"""Unit tests for the policy engine and workflow policies."""

import pytest

from src.policies.policy_engine import PolicyEngine
from src.policies.policy_models import PolicyDecision, WorkflowPolicy
from src.plugins.tooling_metadata import RiskLevel, ToolDefinition


@pytest.fixture
def sample_tool() -> ToolDefinition:
    return ToolDefinition(
        name="sample_tool",
        description="A sample tool",
        risk_level=RiskLevel.MEDIUM,
    )


def test_policy_defaults_allow(sample_tool: ToolDefinition):
    engine = PolicyEngine()
    evaluation = engine.evaluate(workflow_id="unknown", plugin_name="Sample", tool=sample_tool)

    assert evaluation.decision == PolicyDecision.ALLOW


def test_policy_threshold_requires_approval(sample_tool: ToolDefinition):
    policy = WorkflowPolicy(workflow_id="wf", automation_threshold=RiskLevel.LOW)
    engine = PolicyEngine()
    engine.register_policy(policy)

    evaluation = engine.evaluate(workflow_id="wf", plugin_name="Sample", tool=sample_tool)
    assert evaluation.decision == PolicyDecision.REQUIRE_HUMAN_APPROVAL


def test_policy_blocklist(sample_tool: ToolDefinition):
    policy = WorkflowPolicy(workflow_id="wf", blocklist=["sample.sample_tool"])
    engine = PolicyEngine()
    engine.register_policy(policy)

    evaluation = engine.evaluate(workflow_id="wf", plugin_name="Sample", tool=sample_tool)
    assert evaluation.decision == PolicyDecision.BLOCK


def test_policy_explicit_approval(sample_tool: ToolDefinition):
    policy = WorkflowPolicy(workflow_id="wf", approval_required=["sample.sample_tool"])
    engine = PolicyEngine()
    engine.register_policy(policy)

    evaluation = engine.evaluate(workflow_id="wf", plugin_name="Sample", tool=sample_tool)
    assert evaluation.decision == PolicyDecision.REQUIRE_HUMAN_APPROVAL


def test_evaluate_manifest_returns_map(sample_tool: ToolDefinition):
    policy = WorkflowPolicy(workflow_id="wf")
    engine = PolicyEngine()
    engine.register_policy(policy)

    manifest = {"Sample": {sample_tool.name: sample_tool}}
    evaluations = engine.evaluate_manifest(workflow_id="wf", manifest=manifest)

    assert "Sample" in evaluations
    assert sample_tool.name in evaluations["Sample"]
    assert evaluations["Sample"][sample_tool.name].decision in {
        PolicyDecision.ALLOW,
        PolicyDecision.REQUIRE_HUMAN_APPROVAL,
        PolicyDecision.BLOCK,
    }
