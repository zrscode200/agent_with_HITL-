"""Service for initializing and configuring Semantic Kernel with agents and observability."""

import logging
from typing import Optional
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion, OpenAIChatCompletion

from src.agents.agent_factory import AgentFactory
from src.agents.agent_orchestrator import AgentOrchestrator
from src.observability.telemetry_service import TelemetryService
from src.filters.security_filter import SecurityFilter
from src.filters.telemetry_filter import TelemetryFilter
from src.plugins.plugin_manager import PluginManager
from config import Settings


class SemanticKernelService:
    """
    Service for initializing and configuring Semantic Kernel with agents and observability.
    Python equivalent of the C# SemanticKernelService with full feature parity.
    """

    def __init__(
        self,
        settings: Settings,
        logger: Optional[logging.Logger] = None,
        telemetry_service: Optional[TelemetryService] = None
    ):
        """Initialize the Semantic Kernel service."""
        self._settings = settings
        self._logger = logger or logging.getLogger(__name__)
        self._telemetry_service = telemetry_service

        self._kernel: Optional[Kernel] = None
        self._agent_factory: Optional[AgentFactory] = None
        self._agent_orchestrator: Optional[AgentOrchestrator] = None
        self._plugin_manager: Optional[PluginManager] = None

    @property
    def kernel(self) -> Kernel:
        """Get the configured Kernel instance."""
        if self._kernel is None:
            raise ValueError("SemanticKernel service not initialized. Call initialize_async first.")
        return self._kernel

    @property
    def agent_factory(self) -> AgentFactory:
        """Get the agent factory."""
        if self._agent_factory is None:
            raise ValueError("SemanticKernel service not initialized. Call initialize_async first.")
        return self._agent_factory

    @property
    def agent_orchestrator(self) -> AgentOrchestrator:
        """Get the agent orchestrator."""
        if self._agent_orchestrator is None:
            raise ValueError("SemanticKernel service not initialized. Call initialize_async first.")
        return self._agent_orchestrator

    @property
    def plugin_manager(self) -> PluginManager:
        """Get the plugin manager."""
        if self._plugin_manager is None:
            raise ValueError("SemanticKernel service not initialized. Call initialize_async first.")
        return self._plugin_manager

    async def initialize_async(self, http_client=None) -> None:
        """Initialize the Semantic Kernel with configured services."""
        self._logger.info("Initializing Semantic Kernel service...")

        try:
            # Create kernel instance
            self._kernel = Kernel()

            # Configure AI services
            await self._configure_ai_services()

            # Configure observability
            self._configure_observability()

            # Initialize components
            self._agent_factory = AgentFactory(self._kernel, self._logger)
            self._agent_orchestrator = AgentOrchestrator(self._logger)
            self._plugin_manager = PluginManager(self._kernel, self._logger)

            # Register built-in filters
            self._register_filters()

            # Register built-in plugins
            self._plugin_manager.register_all_plugins(http_client)

            self._logger.info("Semantic Kernel service initialized successfully")

        except Exception as ex:
            self._logger.error(f"Failed to initialize Semantic Kernel service: {ex}", exc_info=ex)
            raise

    async def _configure_ai_services(self) -> None:
        """Configure AI services (Azure OpenAI or OpenAI)."""
        # Try Azure OpenAI first
        if self._settings.azure_openai:
            self._logger.info("Configuring Azure OpenAI service")
            chat_service = AzureChatCompletion(
                deployment_name=self._settings.azure_openai.model_id,
                endpoint=self._settings.azure_openai.endpoint,
                api_key=self._settings.azure_openai.api_key,
                api_version=self._settings.azure_openai.api_version,
                service_id="default"
            )
            self._kernel.add_service(chat_service)
            return

        # Fallback to OpenAI
        if self._settings.openai:
            self._logger.info("Configuring OpenAI service")
            chat_service = OpenAIChatCompletion(
                ai_model_id=self._settings.openai.model_id,
                api_key=self._settings.openai.api_key,
                service_id="default"
            )
            self._kernel.add_service(chat_service)
            return

        raise ValueError(
            "No AI service configuration found. Please configure either Azure OpenAI or OpenAI"
        )

    def _configure_observability(self) -> None:
        """Configure observability features."""
        self._logger.info("Configuring observability features")
        # SK's built-in telemetry will automatically hook into Python's logging
        # The TelemetryService will configure OpenTelemetry exporters

    def _register_filters(self) -> None:
        """Register built-in filters for security and telemetry."""
        if self._kernel is None:
            return

        self._logger.info("Registering kernel filters")

        # Add function invocation filters for security and telemetry
        security_filter = SecurityFilter(self._logger)
        self._kernel.add_filter("function_invocation", security_filter)

        if self._telemetry_service:
            telemetry_filter = TelemetryFilter(self._telemetry_service, self._logger)
            self._kernel.add_filter("function_invocation", telemetry_filter)

    async def create_default_agents_async(self) -> None:
        """Create and register a set of default agents."""
        if self._agent_factory is None or self._agent_orchestrator is None:
            raise ValueError("Service not initialized")

        self._logger.info("Creating default agents")

        # Create specialized agents
        document_analyst = self._agent_factory.create_document_analysis_agent()
        approval_coordinator = self._agent_factory.create_approval_coordinator_agent()
        task_orchestrator = self._agent_factory.create_task_orchestrator_agent()

        # Register agents with orchestrator
        self._agent_orchestrator.register_agent(document_analyst)
        self._agent_orchestrator.register_agent(approval_coordinator)
        self._agent_orchestrator.register_agent(task_orchestrator)

        self._logger.info("Default agents created and registered")

    async def validate_configuration_async(self) -> bool:
        """Validate the service configuration."""
        self._logger.info("Validating Semantic Kernel service configuration")

        try:
            # Check AI service configuration
            if not self._settings.azure_openai and not self._settings.openai:
                self._logger.error("No AI service configured")
                return False

            # Validate plugins if manager exists
            if self._plugin_manager:
                validation_result = await self._plugin_manager.validate_plugins_async()
                if not validation_result.is_valid:
                    self._logger.warning(
                        f"Plugin validation failed: {validation_result.failed_plugins}"
                    )

            # Test basic kernel functionality
            if self._kernel:
                # Try to get a service to ensure kernel is properly configured
                try:
                    services = self._kernel.get_services_by_type(object)
                    if not services:
                        self._logger.warning("No services found in kernel")
                except Exception as ex:
                    self._logger.error(f"Kernel service validation failed: {ex}")
                    return False

            self._logger.info("Semantic Kernel service configuration validation completed")
            return True

        except Exception as ex:
            self._logger.error(f"Configuration validation failed: {ex}", exc_info=ex)
            return False

    def get_service_info(self) -> dict:
        """Get information about the configured service."""
        info = {
            "initialized": self._kernel is not None,
            "ai_service": None,
            "agents_count": 0,
            "plugins_count": 0
        }

        if self._settings.azure_openai:
            info["ai_service"] = {
                "type": "Azure OpenAI",
                "model": self._settings.azure_openai.model_id,
                "endpoint": self._settings.azure_openai.endpoint
            }
        elif self._settings.openai:
            info["ai_service"] = {
                "type": "OpenAI",
                "model": self._settings.openai.model_id
            }

        if self._agent_orchestrator:
            info["agents_count"] = len(self._agent_orchestrator.get_all_agents())

        if self._plugin_manager:
            info["plugins_count"] = len(self._plugin_manager.get_registered_plugins())

        return info

    def dispose(self) -> None:
        """Dispose resources."""
        # Python doesn't have explicit dispose, but we can clean up references
        self._kernel = None
        self._agent_factory = None
        self._agent_orchestrator = None
        self._plugin_manager = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize_async()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self.dispose()