"""Human-in-the-loop approval services."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, Optional

from src.plugins.tooling_metadata import RiskLevel
from src.observability.telemetry_service import TelemetryService


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

        prompt = (
            "\nHITL approval required\n"
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

        comment = ""
        if not self._auto_approve:
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


__all__ = [
    "ApprovalRequest",
    "ApprovalDecision",
    "ApprovalService",
    "ConsoleApprovalService",
]
