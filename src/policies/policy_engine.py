"""HITL policy engine that decides how tools can be invoked per workflow."""

from __future__ import annotations

import logging
from typing import Dict, Optional

from src.plugins.tooling_metadata import RiskLevel, ToolDefinition
from .policy_models import PolicyDecision, PolicyEvaluation, WorkflowPolicy, compare_risk


class PolicyEngine:
    """Evaluate tool usage policies across workflows."""

    def __init__(
        self,
        *,
        default_policy: Optional[WorkflowPolicy] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._logger = logger or logging.getLogger(self.__class__.__name__)
        self._default_policy = default_policy or WorkflowPolicy(workflow_id="default")
        self._workflow_policies: Dict[str, WorkflowPolicy] = {
            self._default_policy.workflow_id: self._default_policy
        }

    def register_policy(self, policy: WorkflowPolicy) -> None:
        """Register or overwrite a workflow policy."""
        self._logger.debug("Registering workflow policy: %s", policy.workflow_id)
        self._workflow_policies[policy.workflow_id.lower()] = policy

    def get_policy(self, workflow_id: str) -> WorkflowPolicy:
        """Return the policy for the workflow or the default."""
        return self._workflow_policies.get(workflow_id.lower(), self._default_policy)

    def evaluate(
        self,
        *,
        workflow_id: str,
        plugin_name: str,
        tool: ToolDefinition,
    ) -> PolicyEvaluation:
        """Evaluate a tool invocation for the given workflow."""
        policy = self.get_policy(workflow_id)
        plugin_tool_key = policy.plugin_tool_key(plugin_name, tool.name)

        # explicit blocklist overrides everything
        if policy.is_blocked(plugin_name, tool.name) or tool.risk_level == RiskLevel.CRITICAL:
            rationale = (
                f"Tool {plugin_tool_key} is blocked for workflow {workflow_id}"
                if policy.is_blocked(plugin_name, tool.name)
                else "Critical risk tools are blocked"
            )
            decision = PolicyDecision.BLOCK
        # explicit approval override
        elif policy.requires_approval(plugin_name, tool.name):
            rationale = f"Workflow policy requires human approval for {plugin_tool_key}"
            decision = PolicyDecision.REQUIRE_HUMAN_APPROVAL
        # risk based automation threshold
        else:
            comparison = compare_risk(tool.risk_level, policy.automation_threshold)
            if comparison > 0:
                rationale = (
                    f"Risk level {tool.risk_level.value} exceeds automation threshold "
                    f"{policy.automation_threshold.value}"
                )
                decision = PolicyDecision.REQUIRE_HUMAN_APPROVAL
            else:
                rationale = "Within automation threshold"
                decision = PolicyDecision.ALLOW

        evaluation = PolicyEvaluation(
            workflow_id=workflow_id,
            plugin_name=plugin_name,
            tool=tool,
            decision=decision,
            rationale=rationale,
        )

        self._logger.debug(
            "Policy evaluation for %s (%s): %s - %s",
            plugin_tool_key,
            workflow_id,
            decision.value,
            rationale,
        )

        return evaluation

    def evaluate_manifest(
        self,
        *,
        workflow_id: str,
        manifest: Dict[str, Dict[str, ToolDefinition]],
    ) -> Dict[str, Dict[str, PolicyEvaluation]]:
        """Evaluate all tools for a workflow and return decision map."""
        results: Dict[str, Dict[str, PolicyEvaluation]] = {}
        for plugin_name, tools in manifest.items():
            plugin_results: Dict[str, PolicyEvaluation] = {}
            for tool_name, definition in tools.items():
                plugin_results[tool_name] = self.evaluate(
                    workflow_id=workflow_id,
                    plugin_name=plugin_name,
                    tool=definition,
                )
            results[plugin_name] = plugin_results
        return results


__all__ = ["PolicyEngine"]
