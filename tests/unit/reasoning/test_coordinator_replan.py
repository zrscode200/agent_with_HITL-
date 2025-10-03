"""Tests for PlanReactCoordinator re-planning functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from src.reasoning.plan_react.models import (
    ActionType,
    DivergenceSignal,
    DivergenceSeverity,
    PlanItem,
    PlanReactConfiguration,
    PlanReactPlan,
    PlanReactRequest,
    PlanReactResult,
    ReplanContext,
)
from src.reasoning.plan_react.process import PlanReactCoordinator


class TestPrepareReplanRequest:
    """Test _prepare_replan_request method."""

    def test_prepare_replan_enriches_context(self):
        """Test that replan request includes enriched context."""
        from semantic_kernel import Kernel

        kernel = Kernel()
        config = PlanReactConfiguration()
        coordinator = PlanReactCoordinator(kernel=kernel, config=config)

        original_request = PlanReactRequest(
            task="Test task",
            step_budget=5,
            context={"original": "data"},
            hints=["Hint 1"],
        )

        plan = PlanReactPlan(
            task="Test task",
            rationale="Original rationale",
            step_budget=5,
            allow_step_extension=True,
            plan=[],
        )

        divergence = DivergenceSignal(
            severity=DivergenceSeverity.CRITICAL,
            step_number=2,
            reason="Tool failed",
            observed_state="Error",
            expected_state="Success",
            recommendation=ActionType.REQUEST_REPLAN,
        )

        replan_context = ReplanContext(
            original_plan=plan,
            execution_history=[],
            scratchpad=[
                {"title": "Step 1", "observation": "Success"},
                {"title": "Step 2", "observation": "Failed with error"},
            ],
            divergence=divergence,
            completed_steps=[1],
            remaining_budget=3,
            lessons_learned=["Step 2 failed", "Network timeout"],
        )

        new_request = coordinator._prepare_replan_request(original_request, replan_context)

        # Check enriched context
        assert "replan_context" in new_request.context
        assert new_request.context["replan_context"]["divergence"]["reason"] == "Tool failed"
        assert len(new_request.context["replan_context"]["execution_summary"]) == 2
        assert len(new_request.context["replan_context"]["lessons_learned"]) == 2

        # Check hints include failure info
        assert len(new_request.hints) > len(original_request.hints)
        assert any("Tool failed" in hint for hint in new_request.hints)

        # Check budget increase
        assert new_request.step_budget == replan_context.remaining_budget + 2

    def test_prepare_replan_preserves_original_task(self):
        """Test that replan preserves original task."""
        from semantic_kernel import Kernel

        kernel = Kernel()
        config = PlanReactConfiguration()
        coordinator = PlanReactCoordinator(kernel=kernel, config=config)

        original_request = PlanReactRequest(
            task="Original task",
            step_budget=5,
            context={},
            hints=[],
        )

        replan_context = ReplanContext(
            original_plan=PlanReactPlan(
                task="Original task",
                rationale="Test",
                step_budget=5,
                allow_step_extension=True,
                plan=[],
            ),
            execution_history=[],
            scratchpad=[],
            divergence=DivergenceSignal(
                severity=DivergenceSeverity.CRITICAL,
                step_number=1,
                reason="Test",
                observed_state="Test",
                expected_state="Test",
                recommendation=ActionType.REQUEST_REPLAN,
            ),
            completed_steps=[],
            remaining_budget=3,
            lessons_learned=[],
        )

        new_request = coordinator._prepare_replan_request(original_request, replan_context)

        assert new_request.task == "Original task"


class TestCoordinatorConfiguration:
    """Test coordinator configuration for re-planning."""

    def test_max_replans_configuration(self):
        """Test max_replans configuration."""
        config = PlanReactConfiguration(max_replans=3)
        assert config.max_replans == 3

    def test_enable_auto_replan_configuration(self):
        """Test enable_auto_replan configuration."""
        config = PlanReactConfiguration(enable_auto_replan=False)
        assert config.enable_auto_replan is False

    def test_default_replan_configuration(self):
        """Test default replan configuration values."""
        config = PlanReactConfiguration()
        assert config.max_replans == 2
        assert config.enable_auto_replan is True


class TestReplanContextExtraction:
    """Test extraction of replan context from results."""

    def test_result_with_replan_requested(self):
        """Test result properly signals replan request."""
        plan = PlanReactPlan(
            task="Test", rationale="Test", step_budget=5, allow_step_extension=True, plan=[]
        )

        replan_ctx = ReplanContext(
            original_plan=plan,
            execution_history=[],
            scratchpad=[],
            divergence=DivergenceSignal(
                severity=DivergenceSeverity.CRITICAL,
                step_number=1,
                reason="Failed",
                observed_state="Error",
                expected_state="Success",
                recommendation=ActionType.REQUEST_REPLAN,
            ),
            completed_steps=[],
            remaining_budget=3,
            lessons_learned=["Lesson"],
        )

        result = PlanReactResult(
            task="Test",
            final_response="Halted",
            steps_executed=1,
            plan=plan,
            traces=[],
            replan_requested=True,
            replan_context=replan_ctx,
        )

        assert result.replan_requested is True
        assert result.replan_context is not None
        assert result.replan_context.divergence.severity == DivergenceSeverity.CRITICAL

    def test_result_without_replan(self):
        """Test normal result without replan request."""
        plan = PlanReactPlan(
            task="Test", rationale="Test", step_budget=5, allow_step_extension=True, plan=[]
        )

        result = PlanReactResult(
            task="Test",
            final_response="Success",
            steps_executed=3,
            plan=plan,
            traces=[],
            replan_requested=False,
            replan_context=None,
        )

        assert result.replan_requested is False
        assert result.replan_context is None


class TestReplanContextLessonsExtraction:
    """Test lessons learned extraction logic."""

    def test_lessons_include_divergence_info(self):
        """Test that lessons include divergence information."""
        plan = PlanReactPlan(
            task="Test", rationale="Test", step_budget=5, allow_step_extension=True, plan=[]
        )

        lessons = [
            "Step 1 diverged: Tool execution failed",
            "Step 2 encountered issue: Connection timeout",
            "Critical divergence at step 3: Missing capability",
        ]

        replan_ctx = ReplanContext(
            original_plan=plan,
            execution_history=[],
            scratchpad=[],
            divergence=DivergenceSignal(
                severity=DivergenceSeverity.CRITICAL,
                step_number=3,
                reason="Missing capability",
                observed_state="Error",
                expected_state="Success",
                recommendation=ActionType.REQUEST_REPLAN,
            ),
            completed_steps=[1, 2],
            remaining_budget=2,
            lessons_learned=lessons,
        )

        # Verify lessons are structured correctly
        assert len(replan_ctx.lessons_learned) == 3
        assert any("diverged" in lesson for lesson in replan_ctx.lessons_learned)
        assert any("encountered issue" in lesson for lesson in replan_ctx.lessons_learned)
        assert any("Critical divergence" in lesson for lesson in replan_ctx.lessons_learned)


class TestReplanRequestHints:
    """Test that replan requests include appropriate hints."""

    def test_hints_include_failure_reason(self):
        """Test that new hints include failure information."""
        from semantic_kernel import Kernel

        kernel = Kernel()
        config = PlanReactConfiguration()
        coordinator = PlanReactCoordinator(kernel=kernel, config=config)

        original_request = PlanReactRequest(
            task="Test task", step_budget=5, context={}, hints=["Original hint"]
        )

        replan_context = ReplanContext(
            original_plan=PlanReactPlan(
                task="Test task", rationale="Test", step_budget=5, allow_step_extension=True, plan=[]
            ),
            execution_history=[],
            scratchpad=[],
            divergence=DivergenceSignal(
                severity=DivergenceSeverity.CRITICAL,
                step_number=1,
                reason="Network connection failed",
                observed_state="Timeout",
                expected_state="Connected",
                recommendation=ActionType.REQUEST_REPLAN,
            ),
            completed_steps=[],
            remaining_budget=4,
            lessons_learned=["Network unstable", "Retry needed"],
        )

        new_request = coordinator._prepare_replan_request(original_request, replan_context)

        # Should have original hint plus new ones
        assert len(new_request.hints) >= 3
        assert "Original hint" in new_request.hints

        # Should include failure reason
        assert any("Network connection failed" in hint for hint in new_request.hints)

        # Should include lessons
        assert any("Network unstable" in hint for hint in new_request.hints)


class TestReplanBudgetAdjustment:
    """Test budget adjustments during re-planning."""

    def test_budget_increases_on_replan(self):
        """Test that budget is increased on replan."""
        from semantic_kernel import Kernel

        kernel = Kernel()
        config = PlanReactConfiguration()
        coordinator = PlanReactCoordinator(kernel=kernel, config=config)

        original_request = PlanReactRequest(
            task="Test", step_budget=5, context={}, hints=[]
        )

        replan_context = ReplanContext(
            original_plan=PlanReactPlan(
                task="Test", rationale="Test", step_budget=5, allow_step_extension=True, plan=[]
            ),
            execution_history=[],
            scratchpad=[],
            divergence=DivergenceSignal(
                severity=DivergenceSeverity.CRITICAL,
                step_number=1,
                reason="Test",
                observed_state="Test",
                expected_state="Test",
                recommendation=ActionType.REQUEST_REPLAN,
            ),
            completed_steps=[],
            remaining_budget=2,
            lessons_learned=[],
        )

        new_request = coordinator._prepare_replan_request(original_request, replan_context)

        # Budget should be remaining + 2 extra
        assert new_request.step_budget == replan_context.remaining_budget + 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
