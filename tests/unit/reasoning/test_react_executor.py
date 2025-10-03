"""Tests for ReAct executor with LLM-driven reasoning and re-planning."""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock

from src.reasoning.plan_react.models import (
    ActionDecision,
    ActionType,
    DivergenceSignal,
    DivergenceSeverity,
    ExecutionTrace,
    PlanItem,
    PlanReactPlan,
    PlanReactRequest,
    PlanReactResult,
    ReplanContext,
    StepStatus,
)
from src.reasoning.plan_react.steps_reactive import ReactivePlanReactExecutorStep


class TestModels:
    """Test new model classes."""

    def test_action_decision_creation(self):
        """Test ActionDecision model instantiation."""
        decision = ActionDecision(
            action_type=ActionType.EXECUTE_TOOL,
            tool_name="TestPlugin.TestTool",
            parameters={"param1": "value1"},
            rationale="Test rationale",
            confidence=0.85,
        )
        assert decision.action_type == ActionType.EXECUTE_TOOL
        assert decision.tool_name == "TestPlugin.TestTool"
        assert decision.parameters == {"param1": "value1"}
        assert decision.confidence == 0.85

    def test_action_decision_defaults(self):
        """Test ActionDecision default values."""
        decision = ActionDecision(action_type=ActionType.SKIP_STEP)
        assert decision.tool_name is None
        assert decision.parameters == {}
        assert decision.rationale == ""
        assert decision.confidence == 1.0

    def test_divergence_signal_creation(self):
        """Test DivergenceSignal model."""
        divergence = DivergenceSignal(
            severity=DivergenceSeverity.CRITICAL,
            step_number=2,
            reason="Tool execution failed",
            observed_state="Error: connection timeout",
            expected_state="Successful connection",
            recommendation=ActionType.REQUEST_REPLAN,
            context={"error_code": 500},
        )
        assert divergence.severity == DivergenceSeverity.CRITICAL
        assert divergence.step_number == 2
        assert divergence.recommendation == ActionType.REQUEST_REPLAN
        assert divergence.context["error_code"] == 500

    def test_replan_context_creation(self):
        """Test ReplanContext model."""
        plan = PlanReactPlan(
            task="Test task",
            rationale="Test rationale",
            step_budget=5,
            allow_step_extension=True,
            plan=[],
        )

        divergence = DivergenceSignal(
            severity=DivergenceSeverity.CRITICAL,
            step_number=1,
            reason="Test failure",
            observed_state="Failed",
            expected_state="Success",
            recommendation=ActionType.REQUEST_REPLAN,
        )

        replan_ctx = ReplanContext(
            original_plan=plan,
            execution_history=[],
            scratchpad=[],
            divergence=divergence,
            completed_steps=[1, 2],
            remaining_budget=3,
            lessons_learned=["Lesson 1", "Lesson 2"],
        )

        assert replan_ctx.original_plan == plan
        assert replan_ctx.completed_steps == [1, 2]
        assert len(replan_ctx.lessons_learned) == 2

    def test_plan_react_result_with_replan(self):
        """Test PlanReactResult with replan fields."""
        plan = PlanReactPlan(
            task="Test", rationale="Test", step_budget=5, allow_step_extension=True, plan=[]
        )

        result = PlanReactResult(
            task="Test",
            final_response="Response",
            steps_executed=2,
            plan=plan,
            traces=[],
            replan_requested=True,
            replan_context=None,
        )

        assert result.replan_requested is True
        assert result.extension_requested is False


class TestDivergenceDetection:
    """Test divergence detection logic."""

    def test_detect_tool_failure(self):
        """Test detection of tool execution failures."""
        executor = ReactivePlanReactExecutorStep()

        item = PlanItem(step_number=1, title="Test Step", success_criteria="Success")
        observation = "Tool execution failed: connection timeout"
        action_decision = ActionDecision(
            action_type=ActionType.EXECUTE_TOOL,
            tool_name="TestPlugin.TestTool",
            confidence=0.9,
        )

        divergence = executor._detect_divergence(item, observation, action_decision, [])

        assert divergence is not None
        assert divergence.severity == DivergenceSeverity.MODERATE
        assert "failed" in divergence.reason.lower()
        assert divergence.recommendation == ActionType.REQUEST_REPLAN

    def test_detect_low_confidence_action(self):
        """Test detection of low confidence actions."""
        executor = ReactivePlanReactExecutorStep()

        item = PlanItem(step_number=1, title="Test Step", success_criteria="Success")
        observation = "Executed successfully"
        action_decision = ActionDecision(
            action_type=ActionType.EXECUTE_TOOL, tool_name="TestPlugin.TestTool", confidence=0.3
        )

        divergence = executor._detect_divergence(item, observation, action_decision, [])

        assert divergence is not None
        assert divergence.severity == DivergenceSeverity.MINOR
        assert "low confidence" in divergence.reason.lower()

    def test_detect_replan_request_from_llm(self):
        """Test detection when LLM requests replan."""
        executor = ReactivePlanReactExecutorStep()

        item = PlanItem(step_number=1, title="Test Step", success_criteria="Success")
        observation = "Normal observation"
        action_decision = ActionDecision(
            action_type=ActionType.REQUEST_REPLAN,
            rationale="Plan no longer valid",
            confidence=0.9,
        )

        divergence = executor._detect_divergence(item, observation, action_decision, [])

        assert divergence is not None
        assert divergence.severity == DivergenceSeverity.CRITICAL
        assert "recommended re-planning" in divergence.reason

    def test_no_divergence_on_success(self):
        """Test no divergence detected on successful execution."""
        executor = ReactivePlanReactExecutorStep()

        item = PlanItem(step_number=1, title="Test Step", success_criteria="Success")
        observation = "Tool executed successfully with result: data"
        action_decision = ActionDecision(
            action_type=ActionType.EXECUTE_TOOL, tool_name="TestPlugin.TestTool", confidence=0.9
        )

        divergence = executor._detect_divergence(item, observation, action_decision, [])

        assert divergence is None


class TestBuildReplanContext:
    """Test building replan context."""

    def test_build_replan_context_extracts_lessons(self):
        """Test that lessons are extracted from traces."""
        executor = ReactivePlanReactExecutorStep()

        plan = PlanReactPlan(
            task="Test task",
            rationale="Test",
            step_budget=5,
            allow_step_extension=True,
            plan=[],
        )

        # Create traces with divergences
        trace1 = ExecutionTrace(
            sequence=1,
            thought="Thought 1",
            action="Action 1",
            observation="Failed with error",
            divergence=DivergenceSignal(
                severity=DivergenceSeverity.MINOR,
                step_number=1,
                reason="Minor issue",
                observed_state="Error",
                expected_state="Success",
                recommendation=ActionType.SKIP_STEP,
            ),
        )

        trace2 = ExecutionTrace(
            sequence=2,
            thought="Thought 2",
            action="Action 2",
            observation="Exception occurred",
        )

        traces = [trace1, trace2]
        scratchpad = [
            {"title": "Step 1", "observation": "Failed with error"},
            {"title": "Step 2", "observation": "Exception occurred"},
        ]

        divergence = DivergenceSignal(
            severity=DivergenceSeverity.CRITICAL,
            step_number=2,
            reason="Critical failure",
            observed_state="Exception",
            expected_state="Success",
            recommendation=ActionType.REQUEST_REPLAN,
        )

        replan_ctx = executor._build_replan_context(plan, traces, scratchpad, divergence, {1, 2}, 3)

        assert len(replan_ctx.lessons_learned) > 0
        # Should extract divergence from trace1
        assert any("Step 1 diverged" in lesson for lesson in replan_ctx.lessons_learned)
        # Should extract error from trace2
        assert any("Step 2 encountered issue" in lesson for lesson in replan_ctx.lessons_learned)
        # Should include critical divergence
        assert any("Critical divergence at step 2" in lesson for lesson in replan_ctx.lessons_learned)


class TestEarlyTermination:
    """Test early termination logic."""

    def test_should_terminate_on_completion_keywords(self):
        """Test early termination when completion keywords detected."""
        executor = ReactivePlanReactExecutorStep()

        scratchpad = [
            {"title": "Step 1", "observation": "Started task"},
            {"title": "Step 2", "observation": "Task completed successfully"},
        ]

        traces = []

        should_terminate = executor._should_terminate_early("Test task", traces, scratchpad)
        assert should_terminate is True

    def test_should_not_terminate_on_partial_completion(self):
        """Test no early termination without completion keywords."""
        executor = ReactivePlanReactExecutorStep()

        scratchpad = [
            {"title": "Step 1", "observation": "Started task"},
            {"title": "Step 2", "observation": "Processing data"},
        ]

        traces = []

        should_terminate = executor._should_terminate_early("Test task", traces, scratchpad)
        assert should_terminate is False

    def test_should_not_terminate_on_empty_scratchpad(self):
        """Test no early termination with empty scratchpad."""
        executor = ReactivePlanReactExecutorStep()

        should_terminate = executor._should_terminate_early("Test task", [], [])
        assert should_terminate is False


class TestActionDescriptions:
    """Test action description helpers."""

    def test_describe_action_decision_execute_tool(self):
        """Test describing EXECUTE_TOOL action."""
        executor = ReactivePlanReactExecutorStep()

        item = PlanItem(step_number=1, title="Test Step", success_criteria="Success")
        decision = ActionDecision(
            action_type=ActionType.EXECUTE_TOOL,
            tool_name="TestPlugin.TestTool",
            rationale="Need to fetch data",
        )

        description = executor._describe_action_decision(decision, item)
        assert "Execute tool: TestPlugin.TestTool" in description
        assert "Need to fetch data" in description

    def test_describe_action_decision_skip(self):
        """Test describing SKIP_STEP action."""
        executor = ReactivePlanReactExecutorStep()

        item = PlanItem(step_number=1, title="Test Step", success_criteria="Success")
        decision = ActionDecision(
            action_type=ActionType.SKIP_STEP, rationale="Not applicable"
        )

        description = executor._describe_action_decision(decision, item)
        assert "Skip step" in description
        assert "Not applicable" in description

    def test_describe_action_decision_terminate(self):
        """Test describing TERMINATE action."""
        executor = ReactivePlanReactExecutorStep()

        item = PlanItem(step_number=1, title="Test Step", success_criteria="Success")
        decision = ActionDecision(
            action_type=ActionType.TERMINATE, rationale="Goal achieved"
        )

        description = executor._describe_action_decision(decision, item)
        assert "Terminate execution" in description
        assert "Goal achieved" in description


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
