"""Tool gateway for workflow-scoped tool activation and HITL routing."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

from semantic_kernel import Kernel
from semantic_kernel.functions import KernelFunction

from src.plugins.plugin_manager import PluginManager
from src.plugins.tooling_metadata import ToolDefinition
from src.policies.policy_engine import PolicyEngine
from src.policies.policy_models import PolicyDecision, PolicyEvaluation
from src.observability.telemetry_service import TelemetryService
from src.policies.approval_service import ApprovalService, ApprovalRequest


@dataclass(slots=True)
class ToolExecutionContext:
    """Context describing a selected tool ready for execution."""

    plugin_name: str
    tool_name: str
    definition: ToolDefinition
    policy: PolicyEvaluation
    function: KernelFunction
    approval_required: bool
    approved: bool = False


class ToolGateway:
    """Select and authorize tools per workflow based on policy decisions."""

    def __init__(
        self,
        *,
        kernel: Kernel,
        plugin_manager: PluginManager,
        policy_engine: PolicyEngine,
        approval_service: ApprovalService,
        telemetry: Optional[TelemetryService] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._kernel = kernel
        self._plugin_manager = plugin_manager
        self._policy_engine = policy_engine
        self._approval_service = approval_service
        self._telemetry = telemetry
        self._logger = logger or logging.getLogger(self.__class__.__name__)

    @property
    def approval_service(self) -> ApprovalService:
        return self._approval_service

    def list_authorized_tools(self, workflow_id: str) -> Dict[str, ToolExecutionContext]:
        """Return authorized tools for a workflow keyed by plugin.tool."""
        evaluations = self._plugin_manager.get_tools_for_workflow(
            workflow_id=workflow_id,
            policy_engine=self._policy_engine,
        )

        authorized: Dict[str, ToolExecutionContext] = {}

        for plugin_name, tools in evaluations.items():
            for tool_name, evaluation in tools.items():
                qualified_name = f"{plugin_name}.{tool_name}"
                if evaluation.decision == PolicyDecision.BLOCK:
                    self._logger.debug(
                        "Tool %s blocked for workflow %s", qualified_name, workflow_id
                    )
                    continue

                kernel_function = self._resolve_kernel_function(plugin_name, evaluation.tool)
                if not kernel_function:
                    self._logger.warning(
                        "Kernel function not found for %s (workflow %s)", qualified_name, workflow_id
                    )
                    continue

                evaluation = evaluation

                approval_required = evaluation.decision == PolicyDecision.REQUIRE_HUMAN_APPROVAL

                context = ToolExecutionContext(
                    plugin_name=plugin_name,
                    tool_name=tool_name,
                    definition=evaluation.tool,
                    policy=evaluation,
                    function=kernel_function,
                    approval_required=approval_required,
                    approved=not approval_required,
                )
                authorized[qualified_name] = context

                if self._telemetry:
                    self._record_decision(workflow_id, context)

        return authorized

    def ensure_approval(self, workflow_id: str, context: ToolExecutionContext) -> bool:
        """Request approval if required and update context state."""
        if not context.approval_required:
            return True

        if context.approved:
            return True

        request = ApprovalRequest(
            workflow_id=workflow_id,
            plugin_name=context.plugin_name,
            tool_name=context.tool_name,
            risk_level=context.definition.risk_level,
            rationale=context.policy.rationale,
            metadata=context.definition.tags,
        )
        decision = self._approval_service.request_approval(request)
        context.approved = decision.approved

        if self._telemetry:
            self._telemetry.record_agent_execution(
                agent_name="ToolGateway.Approval",
                duration_seconds=0.0,
                success=decision.approved,
                tags={
                    "workflow_id": workflow_id,
                    "plugin": context.plugin_name,
                    "tool": context.tool_name,
                    "approved": str(decision.approved).lower(),
                    "reviewer": decision.reviewer,
                },
            )

        return context.approved

    def _resolve_kernel_function(
        self,
        plugin_name: str,
        tool: ToolDefinition,
    ) -> Optional[KernelFunction]:
        try:
            return self._kernel.get_function(plugin_name, tool.name)
        except Exception as ex:  # pragma: no cover - guard for API changes
            self._logger.error(
                "Failed to resolve function for %s.%s: %s",
                plugin_name,
                tool.name,
                ex,
            )
            return None

    def _record_decision(self, workflow_id: str, context: ToolExecutionContext) -> None:
        if not self._telemetry:
            return

        tags = {
            "workflow_id": workflow_id,
            "plugin": context.plugin_name,
            "tool": context.tool_name,
            "risk_level": context.definition.risk_level.value,
            "decision": context.policy.decision.value,
            }
        self._telemetry.record_agent_execution(
            agent_name="ToolGateway",
            duration_seconds=0.0,
            success=context.policy.decision != PolicyDecision.BLOCK,
            tags=tags,
        )


__all__ = ["ToolGateway", "ToolExecutionContext"]
