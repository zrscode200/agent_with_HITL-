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
from src.policies.approval_service import ConsoleApprovalService
from src.context.workflow_context import WorkflowContextManager
from src.reasoning.plan_react.process import PlanReactCoordinator


@pytest.fixture
async def gateway() -> ToolGateway:
    kernel = Kernel()
    manager = PluginManager(kernel, logging.getLogger("test"))
    manager.register_plugin(DocumentProcessingPlugin(logging.getLogger("doc")))

    policy_engine = PolicyEngine()
    workflow_id = PlanReactCoordinator.WORKFLOW_ID
    policy_engine.register_policy(
        WorkflowPolicy(
            workflow_id=workflow_id,
            automation_threshold=RiskLevel.MEDIUM,
            approval_required=["DocumentProcessing.validate_document"],
        )
    )

    approval_service = ConsoleApprovalService(auto_approve=True)
    context_manager = WorkflowContextManager()

    gateway = ToolGateway(
        kernel=kernel,
        plugin_manager=manager,
        policy_engine=policy_engine,
        approval_service=approval_service,
        context_manager=context_manager,
        logger=logging.getLogger("gateway"),
    )
    gateway._test_workflow_id = workflow_id  # type: ignore[attr-defined]
    return gateway


def test_authorized_tools_returns_manifest(gateway: ToolGateway):
    tools = gateway.list_authorized_tools("demo")
    assert "DocumentProcessing.validate_document" in tools


def test_policy_decision_exposed(gateway: ToolGateway):
    tools = gateway.list_authorized_tools("demo")
    decision = tools["DocumentProcessing.validate_document"].policy.decision
    assert decision in {PolicyDecision.ALLOW, PolicyDecision.REQUIRE_HUMAN_APPROVAL}


def test_ensure_approval_resolves(gateway: ToolGateway):
    workflow_id = getattr(gateway, "_test_workflow_id", PlanReactCoordinator.WORKFLOW_ID)
    tools = gateway.list_authorized_tools(workflow_id)
    context = tools["DocumentProcessing.validate_document"]
    approved = gateway.ensure_approval(workflow_id, context)
    assert approved is True
    assert context.approved is True
    assembled = gateway._context_manager.assemble(workflow_id, clear_notes=False)
    assert "Human Notes" in assembled.as_prompt()
