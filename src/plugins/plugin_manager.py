"""Manager for registering and organizing custom plugins with the Semantic Kernel."""

import logging
import inspect
from typing import Dict, Any, List, Optional, Type
from datetime import datetime
from dataclasses import dataclass
from semantic_kernel import Kernel

from .base_plugin import BasePlugin
from .tooling_metadata import PluginMetadata, ToolDefinition
from src.policies.policy_engine import PolicyEngine
from src.policies.policy_models import PolicyDecision, PolicyEvaluation


@dataclass
class PluginInfo:
    """Information about a registered plugin."""
    name: str
    description: str
    function_count: int
    functions: List[str]
    metadata: PluginMetadata


@dataclass
class PluginValidationResult:
    """Result of plugin validation."""
    total_plugins: int
    successful_plugins: List[str]
    failed_plugins: Dict[str, str]
    is_valid: bool
    validated_at: datetime


class PluginManager:
    """
    Manager for registering and organizing custom plugins with the Semantic Kernel.
    Python equivalent of the C# PluginManager with full feature parity.
    """

    def __init__(self, kernel: Kernel, logger: Optional[logging.Logger] = None):
        """Initialize the plugin manager."""
        if kernel is None:
            raise ValueError("kernel cannot be None")

        self._kernel = kernel
        self._logger = logger or logging.getLogger(__name__)
        self._registered_plugins: Dict[str, BasePlugin] = {}

    def register_plugin(self, plugin_instance: BasePlugin, plugin_name: Optional[str] = None) -> None:
        """Register a plugin instance with the kernel."""
        if plugin_instance is None:
            raise ValueError("plugin_instance cannot be None")

        name = plugin_name or plugin_instance.plugin_name
        self._logger.info(f"Registering plugin: {name}")

        try:
            # Import the plugin into the kernel
            self._kernel.add_plugin(plugin_instance, plugin_name=name)

            # Store reference for management
            self._registered_plugins[name] = plugin_instance

            manifest = plugin_instance.get_plugin_metadata()
            function_count = len(manifest.tools)
            self._logger.info(
                "Successfully registered plugin: %s with %d function(s)", name, function_count
            )

        except Exception as ex:
            self._logger.error(f"Failed to register plugin: {name}", exc_info=ex)
            raise

    def register_plugin_type(self, plugin_class: Type[BasePlugin], *args, **kwargs) -> None:
        """Register a plugin by creating an instance of the plugin class."""
        try:
            plugin_instance = plugin_class(*args, **kwargs)
            self.register_plugin(plugin_instance)
        except Exception as ex:
            self._logger.error(f"Failed to create and register plugin of type {plugin_class.__name__}", exc_info=ex)
            raise

    def register_all_plugins(self, http_client=None) -> None:
        """Register all available built-in plugins automatically."""
        self._logger.info("Auto-registering all available plugins")

        try:
            # Register built-in plugins
            self._register_built_in_plugins(http_client)

            self._logger.info(f"Auto-registration completed. Total plugins: {len(self._registered_plugins)}")

        except Exception as ex:
            self._logger.error("Failed during auto-registration of plugins", exc_info=ex)
            raise

    def get_registered_plugins(self) -> Dict[str, PluginInfo]:
        """Get information about all registered plugins."""
        plugin_info = {}

        for name, plugin in self._registered_plugins.items():
            metadata = plugin.get_plugin_metadata()
            plugin_info[name] = PluginInfo(
                name=metadata.name,
                description=metadata.description,
                function_count=len(metadata.tools),
                functions=list(metadata.tools.keys()),
                metadata=metadata,
            )

        return plugin_info

    def get_plugin(self, plugin_name: str) -> Optional[BasePlugin]:
        """Get a specific plugin instance by name."""
        return self._registered_plugins.get(plugin_name)

    def unregister_plugin(self, plugin_name: str) -> bool:
        """Unregister a plugin from the kernel."""
        if plugin_name not in self._registered_plugins:
            self._logger.warning(f"Attempted to unregister non-existent plugin: {plugin_name}")
            return False

        try:
            # Remove from registered plugins
            del self._registered_plugins[plugin_name]

            # Note: SK Python may not have direct plugin removal API
            # This would depend on the specific SK Python implementation
            self._logger.info(f"Unregistered plugin: {plugin_name}")
            return True

        except Exception as ex:
            self._logger.error(f"Failed to unregister plugin: {plugin_name}", exc_info=ex)
            return False

    async def validate_plugins_async(self) -> PluginValidationResult:
        """Validate that all registered plugins are functioning correctly."""
        self._logger.info("Validating all registered plugins")

        result = PluginValidationResult(
            total_plugins=len(self._registered_plugins),
            successful_plugins=[],
            failed_plugins={},
            is_valid=True,
            validated_at=datetime.utcnow()
        )

        for name, plugin in self._registered_plugins.items():
            try:
                manifest = plugin.get_plugin_metadata()
                function_count = len(manifest.tools)
                if function_count > 0:
                    result.successful_plugins.append(name)
                    self._logger.debug(
                        f"Plugin {name} validated successfully with {function_count} functions"
                    )
                else:
                    result.failed_plugins[name] = "No functions found"
                    self._logger.warning(f"Plugin {name} has no functions")

            except Exception as ex:
                result.failed_plugins[name] = str(ex)
                self._logger.error(f"Plugin {name} validation failed", exc_info=ex)

        result.is_valid = len(result.failed_plugins) == 0
        self._logger.info(
            f"Plugin validation completed. Success: {len(result.successful_plugins)}, "
            f"Failed: {len(result.failed_plugins)}"
        )

        return result

    def _register_built_in_plugins(self, http_client=None) -> None:
        """Register built-in plugins."""
        try:
            # Register DocumentProcessingPlugin
            from .document_processing_plugin import DocumentProcessingPlugin
            document_plugin = DocumentProcessingPlugin(self._logger)
            self.register_plugin(document_plugin)

            # Register HttpWebPlugin
            from .http_web_plugin import HttpWebPlugin
            http_plugin = HttpWebPlugin(http_client, self._logger)
            self.register_plugin(http_plugin)

            # Register WifiDiagnosticsPlugin if data directory exists
            try:
                from .wifi_diagnostics_plugin import WifiDiagnosticsPlugin

                wifi_plugin = WifiDiagnosticsPlugin(self._logger)
                self.register_plugin(wifi_plugin)
            except (ImportError, FileNotFoundError):
                self._logger.debug("WifiDiagnosticsPlugin not available; skipping")

            self._logger.info("Built-in plugins registered successfully")

        except Exception as ex:
            self._logger.error("Failed to register built-in plugins", exc_info=ex)
            raise

    def get_tool_manifest(self) -> Dict[str, Dict[str, ToolDefinition]]:
        """Return a manifest of plugin -> tool definitions for governance layers."""
        manifest: Dict[str, Dict[str, ToolDefinition]] = {}
        for name, plugin in self._registered_plugins.items():
            metadata = plugin.get_plugin_metadata()
            manifest[name] = metadata.tools
        return manifest

    def get_tools_for_workflow(
        self,
        *,
        workflow_id: str,
        policy_engine: PolicyEngine,
    ) -> Dict[str, Dict[str, PolicyEvaluation]]:
        """Evaluate all tools for a workflow and return policy decisions."""
        manifest = self.get_tool_manifest()
        return policy_engine.evaluate_manifest(workflow_id=workflow_id, manifest=manifest)
