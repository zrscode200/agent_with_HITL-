"""Tests for the ToolGateway workflow scoping."""

import logging

import pytest
from semantic_kernel import Kernel

from src.plugins.plugin_manager import PluginManager
from src.plugins.document_processing_plugin import DocumentProcessingPlugin
from src.policies.policy_engine import PolicyEngine
from src.policies.policy_models import PolicyDecision, WorkflowPolicy
from src.plugins.tooling_metadata import RiskLevel
from src.runtime.tool_gateway import ToolGateway


@pytest.fixture
async def gateway() -> ToolGateway:
    kernel = Kernel()
    manager = PluginManager(kernel, logging.getLogger("test"))
    manager.register_plugin(DocumentProcessingPlugin(logging.getLogger("doc")))

    policy_engine = PolicyEngine()
    policy_engine.register_policy(
        WorkflowPolicy(
            workflow_id="demo",
            automation_threshold=RiskLevel.MEDIUM,
            approval_required=["DocumentProcessing.validate_document"],
        )
    )

    return ToolGateway(
        kernel=kernel,
        plugin_manager=manager,
        policy_engine=policy_engine,
        logger=logging.getLogger("gateway"),
    )


def test_authorized_tools_returns_manifest(gateway: ToolGateway):
    tools = gateway.list_authorized_tools("demo")
    assert "DocumentProcessing.validate_document" in tools


def test_policy_decision_exposed(gateway: ToolGateway):
    tools = gateway.list_authorized_tools("demo")
    decision = tools["DocumentProcessing.validate_document"].policy.decision
    assert decision in {PolicyDecision.ALLOW, PolicyDecision.REQUIRE_HUMAN_APPROVAL}
