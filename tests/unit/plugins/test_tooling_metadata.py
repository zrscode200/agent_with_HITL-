"""Tests for plugin metadata and tooling descriptors."""

import logging

from src.plugins.base_plugin import BasePlugin
from src.plugins.tooling_metadata import ApprovalRequirement, RiskLevel, ToolDefinition, ToolInput, tool_spec
from src.plugins.plugin_manager import PluginManager
from src.plugins.document_processing_plugin import DocumentProcessingPlugin
from semantic_kernel import Kernel
from semantic_kernel.functions.kernel_function_decorator import kernel_function


class _SamplePlugin(BasePlugin):
    @property
    def plugin_name(self) -> str:
        return "Sample"

    @property
    def plugin_description(self) -> str:
        return "Sample plugin for testing"

    @tool_spec(
        description="Simple echo tool",
        inputs=[ToolInput(name="value", description="Value to echo")],
        risk_level=RiskLevel.LOW,
    )
    @kernel_function(name="echo", description="Echoes the provided value")
    async def echo_async(self, value: str) -> str:
        return value


def test_base_plugin_collects_metadata_defaults():
    plugin = _SamplePlugin()
    metadata = plugin.get_plugin_metadata()

    assert metadata.name == "Sample"
    assert "echo" in metadata.tools
    tool = metadata.tools["echo"]
    assert tool.risk_level == RiskLevel.LOW
    assert tool.inputs[0].name == "value"
    assert tool.field_descriptions == {}


def test_document_processing_plugin_declares_risks():
    plugin = DocumentProcessingPlugin(logging.getLogger("test"))
    metadata = plugin.get_plugin_metadata()

    assert len(metadata.tools) == 4
    assert metadata.tools["validate_document"].approval == ApprovalRequirement.POLICY
    assert metadata.tools["validate_document"].risk_level == RiskLevel.HIGH
    assert "issues" in metadata.tools["validate_document"].field_descriptions


def test_plugin_manager_manifest_exposes_tools():
    kernel = Kernel()
    manager = PluginManager(kernel)
    manager.register_plugin(_SamplePlugin())

    manifest = manager.get_tool_manifest()
    assert "Sample" in manifest
    assert isinstance(manifest["Sample"]["echo"], ToolDefinition)
