"""
AI Agent Platform with Human-in-the-Loop Integration

A comprehensive AI agent platform built on Microsoft's Semantic Kernel with
integrated Human-in-the-Loop workflows, custom tools, and enterprise-grade observability.

This Python implementation provides full feature parity with the C# version, including:
- Multi-Agent Orchestration using SK's GA Agent Framework
- Human-in-the-Loop workflows with approval gates
- Custom plugin system with built-in security filters
- Enterprise observability with OpenTelemetry compliance
- Comprehensive testing and documentation

Usage:
    from src.services.semantic_kernel_service import SemanticKernelService
    from src.config import Settings

    settings = Settings()
    async with SemanticKernelService(settings) as service:
        # Your agent platform code here
        pass
"""

__version__ = "1.0.0"
__author__ = "AI Agent Platform Team"
__email__ = "support@agentplatform.com"

# Key exports - Note: config is at root level now
# from .config import Settings  # Config is now at project root
from .services.semantic_kernel_service import SemanticKernelService
from .agents.agent_factory import AgentFactory
from .agents.agent_orchestrator import AgentOrchestrator
from .plugins.plugin_manager import PluginManager
from .observability.telemetry_service import TelemetryService

__all__ = [
    # "Settings",  # Config is at root level
    "SemanticKernelService",
    "AgentFactory",
    "AgentOrchestrator",
    "PluginManager",
    "TelemetryService"
]