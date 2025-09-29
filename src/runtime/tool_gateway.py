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


@dataclass(slots=True)
class ToolExecutionContext:
    """Context describing a selected tool ready for execution."""

    plugin_name: str
    tool_name: str
    definition: ToolDefinition
    policy: PolicyEvaluation
    function: KernelFunction


class ToolGateway:
    """Select and authorize tools per workflow based on policy decisions."""

    def __init__(
        self,
        *,
        kernel: Kernel,
        plugin_manager: PluginManager,
        policy_engine: PolicyEngine,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._kernel = kernel
        self._plugin_manager = plugin_manager
        self._policy_engine = policy_engine
        self._logger = logger or logging.getLogger(self.__class__.__name__)

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

                authorized[qualified_name] = ToolExecutionContext(
                    plugin_name=plugin_name,
                    tool_name=tool_name,
                    definition=evaluation.tool,
                    policy=evaluation,
                    function=kernel_function,
                )

        return authorized

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


__all__ = ["ToolGateway", "ToolExecutionContext"]
