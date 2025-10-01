"""Human-in-the-loop approval services."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from src.plugins.tooling_metadata import RiskLevel
from src.observability.telemetry_service import TelemetryService
from src.policies.policy_models import ApprovalType


@dataclass(slots=True)
class ApprovalRequest:
    """Information sent to a reviewer before invoking a tool."""

    workflow_id: str
    plugin_name: str
    tool_name: str
    risk_level: RiskLevel
    rationale: str
    metadata: Dict[str, str] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Enhanced: distinguish approval types and phases
    approval_type: ApprovalType = ApprovalType.TOOL_EXECUTION
    phase: str = "execution"  # "strategic", "tactical", "execution"
    planning_context: Optional[Dict[str, Any]] = None


@dataclass(slots=True)
class ApprovalDecision:
    """Outcome of an approval request."""

    request_id: str
    approved: bool
    reviewer: str
    reason: Optional[str] = None
    decided_at: datetime = field(default_factory=datetime.utcnow)


class ApprovalService:
    """Abstract approval service."""

    def request_approval(self, request: ApprovalRequest) -> ApprovalDecision:  # pragma: no cover - interface
        raise NotImplementedError


class ConsoleApprovalService(ApprovalService):
    """Simple approval service that prompts on the console."""

    def __init__(
        self,
        *,
        input_fn: Callable[[str], str] | None = None,
        auto_approve: bool = False,
        telemetry: Optional[TelemetryService] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._input_fn = input_fn or input
        self._auto_approve = auto_approve
        self._telemetry = telemetry
        self._logger = logger or logging.getLogger(self.__class__.__name__)

    def request_approval(self, request: ApprovalRequest) -> ApprovalDecision:
        if self._auto_approve:
            self._logger.info(
                "Auto-approving %s.%s for workflow %s",
                request.plugin_name,
                request.tool_name,
                request.workflow_id,
            )
            return ApprovalDecision(
                request_id=request.request_id,
                approved=True,
                reviewer="auto",
                reason="auto_approve enabled",
            )

        # Route to appropriate handler based on approval type
        if request.approval_type == ApprovalType.TACTICAL_FEASIBILITY:
            return self._handle_feasibility_approval(request)
        elif request.approval_type == ApprovalType.STRATEGIC_REVIEW:
            return self._handle_strategic_review(request)
        elif request.approval_type == ApprovalType.PLUGIN_INSTALLATION:
            return self._handle_plugin_approval(request)
        elif request.approval_type == ApprovalType.RUNTIME_DATA:
            return self._handle_runtime_data_request(request)
        else:
            # Default: tool execution approval
            return self._handle_tool_execution_approval(request)

    def _handle_tool_execution_approval(self, request: ApprovalRequest) -> ApprovalDecision:
        """Handle runtime tool execution approvals (existing behavior)."""
        prompt = (
            "\n" + "="*70 + "\n"
            "HITL APPROVAL REQUIRED\n"
            "="*70 + "\n"
            f"Workflow: {request.workflow_id}\n"
            f"Tool: {request.plugin_name}.{request.tool_name}\n"
            f"Risk: {request.risk_level.value}\n"
            f"Rationale: {request.rationale}\n"
        )
        if request.metadata:
            prompt += "Metadata:\n"
            for key, value in request.metadata.items():
                prompt += f"  - {key}: {value}\n"
        prompt += "Approve? [y/N]: "

        try:
            answer = self._input_fn(prompt).strip().lower()
        except EOFError:
            answer = ""

        approved = answer in {"y", "yes"}
        reviewer = "console"

        comment = self._input_fn("Optional note for context (press Enter to skip): ").strip()
        reason = comment or ("approved via console" if approved else "denied via console")

        self._logger.info(
            "Approval %s for %s.%s (workflow %s)",
            "granted" if approved else "denied",
            request.plugin_name,
            request.tool_name,
            request.workflow_id,
        )

        return ApprovalDecision(
            request_id=request.request_id,
            approved=approved,
            reviewer=reviewer,
            reason=reason,
        )

    def _handle_feasibility_approval(self, request: ApprovalRequest) -> ApprovalDecision:
        """Handle tactical planning gap approvals."""
        ctx = request.planning_context or {}

        prompt = (
            "\n" + "="*70 + "\n"
            "🔧 TACTICAL PLANNING DECISION\n"
            "="*70 + "\n"
            f"Workflow: {request.workflow_id}\n"
            f"Phase: {request.phase}\n"
            f"Strategic Step: {ctx.get('strategic_step', 'N/A')}\n"
            f"Required Capability: {ctx.get('required_capability', 'N/A')}\n"
            f"Issue: {ctx.get('gap_reason', 'N/A')}\n"
            f"Confidence: {ctx.get('confidence', 0.0):.2f}\n"
        )

        if ctx.get('suggested_plugin'):
            prompt += f"Suggested Plugin: {ctx['suggested_plugin']}\n"

        prompt += (
            "\nOptions:\n"
            "  [skip]      - Skip this step entirely\n"
            "  [manual]    - Mark as manual execution (I'll do it)\n"
            "  [alternate] - I'll suggest an alternative approach\n"
        )

        if ctx.get('suggested_plugin'):
            prompt += "  [plugin]    - Queue plugin for installation (ops review)\n"

        prompt += "\nYour decision: "

        try:
            choice = self._input_fn(prompt).strip().lower()
        except EOFError:
            choice = "skip"

        # Parse choice
        if choice in ["skip", "s"]:
            approved = False
            reason = "Human chose to skip this step"
        elif choice in ["manual", "m"]:
            approved = True
            reason = "Human will execute manually"
        elif choice in ["alternate", "a", "alternative"]:
            alternate = self._input_fn("Describe alternative approach: ").strip()
            approved = True
            reason = f"Human provided alternative: {alternate}"
        elif choice in ["plugin", "p"] and ctx.get('suggested_plugin'):
            approved = True
            reason = f"Human approved plugin queue: {ctx['suggested_plugin']}"
        else:
            approved = False
            reason = "Invalid choice; defaulting to skip"

        # Optional: capture additional notes
        note = self._input_fn("Additional notes (optional, press Enter to skip): ").strip()
        if note:
            reason = f"{reason}. Notes: {note}"

        return ApprovalDecision(
            request_id=request.request_id,
            approved=approved,
            reviewer="console",
            reason=reason,
        )

    def _handle_strategic_review(self, request: ApprovalRequest) -> ApprovalDecision:
        """Handle strategic plan reviews."""
        ctx = request.planning_context or {}

        prompt = (
            "\n" + "="*70 + "\n"
            "📋 STRATEGIC PLAN REVIEW\n"
            "="*70 + "\n"
            f"Workflow: {request.workflow_id}\n"
            f"Task: {ctx.get('task', 'N/A')}\n"
            f"Plan Steps: {ctx.get('step_count', 0)}\n"
            "\n"
        )

        if ctx.get('plan_summary'):
            prompt += f"Plan Summary:\n{ctx['plan_summary']}\n\n"

        prompt += "Approve this strategic approach? [y/N]: "

        try:
            answer = self._input_fn(prompt).strip().lower()
        except EOFError:
            answer = ""

        approved = answer in {"y", "yes"}
        note = self._input_fn("Feedback or revisions (press Enter to skip): ").strip()
        reason = note or ("strategic plan approved" if approved else "strategic plan rejected")

        return ApprovalDecision(
            request_id=request.request_id,
            approved=approved,
            reviewer="console",
            reason=reason,
        )

    def _handle_plugin_approval(self, request: ApprovalRequest) -> ApprovalDecision:
        """Handle plugin installation suggestions."""
        ctx = request.planning_context or {}

        prompt = (
            "\n" + "="*70 + "\n"
            "📦 PLUGIN INSTALLATION SUGGESTION\n"
            "="*70 + "\n"
            f"Suggested Plugin: {ctx.get('plugin_name', 'N/A')}\n"
            f"Required For: {ctx.get('capability', 'N/A')}\n"
            f"Rationale: {request.rationale}\n"
            "\nQueue for ops review? [y/N]: "
        )

        try:
            answer = self._input_fn(prompt).strip().lower()
        except EOFError:
            answer = ""

        approved = answer in {"y", "yes"}
        reason = "plugin queued for ops review" if approved else "plugin suggestion declined"

        return ApprovalDecision(
            request_id=request.request_id,
            approved=approved,
            reviewer="console",
            reason=reason,
        )

    def _handle_runtime_data_request(self, request: ApprovalRequest) -> ApprovalDecision:
        """Handle runtime data input requests."""
        ctx = request.planning_context or {}

        prompt = (
            "\n" + "="*70 + "\n"
            "📋 DATA NEEDED\n"
            "="*70 + "\n"
            f"Step: {ctx.get('step_title', 'N/A')}\n"
            f"Required Data: {ctx.get('required_fields', 'N/A')}\n"
            "\nProvide data? [y/N]: "
        )

        try:
            answer = self._input_fn(prompt).strip().lower()
        except EOFError:
            answer = ""

        approved = answer in {"y", "yes"}

        # If approved, collect the data
        reason = "data provided" if approved else "data request declined"

        return ApprovalDecision(
            request_id=request.request_id,
            approved=approved,
            reviewer="console",
            reason=reason,
        )


__all__ = [
    "ApprovalRequest",
    "ApprovalDecision",
    "ApprovalService",
    "ConsoleApprovalService",
]
