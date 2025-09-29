"""Agent runtime builder that composes Semantic Kernel services, plugins, and reasoning workflows."""

from __future__ import annotations

import logging
from typing import Optional

from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion, OpenAIChatCompletion

from config import Settings
from src.agents.agent_factory import AgentFactory
from src.agents.agent_orchestrator import AgentOrchestrator
from src.filters.security_filter import SecurityFilter
from src.filters.telemetry_filter import TelemetryFilter
from src.observability.telemetry_service import TelemetryService
from src.plugins.plugin_manager import PluginManager
from src.plugins.tooling_metadata import RiskLevel
from src.policies.policy_engine import PolicyEngine
from src.policies.policy_models import WorkflowPolicy
from src.reasoning.plan_react.process import PlanReactCoordinator, PlanReactConfiguration
from src.runtime.runtime_types import AgentRuntime
from src.runtime.tool_gateway import ToolGateway


class AgentRuntimeBuilder:
    """Factory for assembling the agent runtime with built-in guardrails and reasoning flows."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        *,
        telemetry_service: Optional[TelemetryService] = None,
        logger: Optional[logging.Logger] = None,
        http_client: Optional[object] = None,
    ) -> None:
        self._settings = settings or Settings()
        self._telemetry_service = telemetry_service
        self._logger = logger or logging.getLogger(self.__class__.__name__)
        self._http_client = http_client

        self._kernel: Kernel = Kernel()
        self._runtime: Optional[AgentRuntime] = None

    async def build(self) -> AgentRuntime:
        """Construct the runtime and return initialized components."""
        await self._configure_ai_service()
        self._register_filters()

        plugin_manager = PluginManager(self._kernel, self._logger)
        plugin_manager.register_all_plugins(self._http_client)

        agent_factory = AgentFactory(self._kernel, self._logger)
        agent_orchestrator = AgentOrchestrator(self._logger)

        plan_react = PlanReactCoordinator(
            kernel=self._kernel,
            config=PlanReactConfiguration(),
            telemetry_service=self._telemetry_service,
            logger=self._logger.getChild("PlanReact"),
        )

        policy_engine = self._build_policy_engine(plugin_manager)

        tool_gateway = ToolGateway(
            kernel=self._kernel,
            plugin_manager=plugin_manager,
            policy_engine=policy_engine,
            logger=self._logger.getChild("ToolGateway"),
        )

        runtime = AgentRuntime(
            kernel=self._kernel,
            plugin_manager=plugin_manager,
            agent_factory=agent_factory,
            agent_orchestrator=agent_orchestrator,
            plan_react=plan_react,
            policy_engine=policy_engine,
            tool_gateway=tool_gateway,
            telemetry_service=self._telemetry_service,
        )

        await self._create_default_agents(runtime)
        self._runtime = runtime
        return runtime

    async def __aenter__(self) -> AgentRuntime:
        return await self.build()

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._runtime:
            self._runtime.dispose()
        self._runtime = None

    async def _configure_ai_service(self) -> None:
        """Wire Azure OpenAI or OpenAI chat completion services if configured."""
        if self._settings.azure_openai:
            azure = self._settings.azure_openai
            self._logger.info("Configuring Azure OpenAI chat completion service (%s)", azure.model_id)
            chat_service = AzureChatCompletion(
                deployment_name=azure.model_id,
                endpoint=azure.endpoint,
                api_key=azure.api_key,
                api_version=azure.api_version,
                service_id="default",
            )
            self._kernel.add_service(chat_service)
            return

        if self._settings.openai:
            openai = self._settings.openai
            self._logger.info("Configuring OpenAI chat completion service (%s)", openai.model_id)
            chat_service = OpenAIChatCompletion(
                ai_model_id=openai.model_id,
                api_key=openai.api_key,
                service_id="default",
            )
            self._kernel.add_service(chat_service)
            return

        self._logger.warning(
            "No chat completion service configured. Plan/ReAct flows will use heuristic fallbacks."
        )

    def _register_filters(self) -> None:
        """Register security and telemetry filters with the kernel."""
        security_filter = SecurityFilter(self._logger)
        self._kernel.add_filter("function_invocation", security_filter)

        if self._telemetry_service:
            telemetry_filter = TelemetryFilter(self._telemetry_service, self._logger)
            self._kernel.add_filter("function_invocation", telemetry_filter)

    def _build_policy_engine(self, plugin_manager: PluginManager) -> PolicyEngine:
        """Create the policy engine with default workflow policies."""
        policy_logger = self._logger.getChild("PolicyEngine")

        default_policy = WorkflowPolicy(
            workflow_id="default",
            automation_threshold=RiskLevel.MEDIUM,
            notes="Default automation threshold applies to workflows without explicit policies.",
        )

        policy_engine = PolicyEngine(default_policy=default_policy, logger=policy_logger)

        plan_react_policy = WorkflowPolicy(
            workflow_id=PlanReactCoordinator.WORKFLOW_ID,
            automation_threshold=RiskLevel.MEDIUM,
            approval_required=["documentprocessing.validate_document"],
            notes="Require approval for high-risk validation steps in plan-react workflows.",
        )
        policy_engine.register_policy(plan_react_policy)

        # Trigger an eager evaluation so issues surface early during startup logs.
        decisions = policy_engine.evaluate_manifest(
            workflow_id=PlanReactCoordinator.WORKFLOW_ID,
            manifest=plugin_manager.get_tool_manifest(),
        )
        policy_logger.debug("Initial policy evaluation for plan-react: %s", decisions)

        return policy_engine

    async def _create_default_agents(self, runtime: AgentRuntime) -> None:
        """Provision baseline agents for demos and regression coverage."""
        # Existing defaults were synchronous creations. Reuse the factory to stay backward compatible.
        document_analyst = runtime.agent_factory.create_document_analysis_agent()
        approval_coordinator = runtime.agent_factory.create_approval_coordinator_agent()
        task_orchestrator = runtime.agent_factory.create_task_orchestrator_agent()

        runtime.agent_orchestrator.register_agent(document_analyst)
        runtime.agent_orchestrator.register_agent(approval_coordinator)
        runtime.agent_orchestrator.register_agent(task_orchestrator)


__all__ = ["AgentRuntimeBuilder"]
