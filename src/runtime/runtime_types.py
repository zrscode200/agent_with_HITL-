"""Runtime data structures for the agent platform."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from semantic_kernel import Kernel

from src.agents.agent_factory import AgentFactory
from src.agents.agent_orchestrator import AgentOrchestrator
from src.observability.telemetry_service import TelemetryService
from src.plugins.plugin_manager import PluginManager
from src.policies.policy_engine import PolicyEngine
from src.reasoning.plan_react.process import PlanReactCoordinator
from src.runtime.tool_gateway import ToolGateway
from src.policies.approval_service import ApprovalService


@dataclass(slots=True)
class AgentRuntime:
    """Aggregated runtime components made available to contributors."""

    kernel: Kernel
    plugin_manager: PluginManager
    agent_factory: AgentFactory
    agent_orchestrator: AgentOrchestrator
    plan_react: PlanReactCoordinator
    policy_engine: PolicyEngine
    tool_gateway: ToolGateway
    approval_service: ApprovalService
    telemetry_service: Optional[TelemetryService] = None

    def dispose(self) -> None:
        """Release kernel-scoped resources."""
        self.plugin_manager = None  # type: ignore[assignment]
        self.agent_factory = None  # type: ignore[assignment]
        self.agent_orchestrator = None  # type: ignore[assignment]
        self.plan_react = None  # type: ignore[assignment]
        self.policy_engine = None  # type: ignore[assignment]
        self.tool_gateway = None  # type: ignore[assignment]
        self.approval_service = None  # type: ignore[assignment]
        self.kernel.remove_all_services()
