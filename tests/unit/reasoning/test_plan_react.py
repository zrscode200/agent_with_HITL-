import pytest

from semantic_kernel import Kernel

from src.reasoning.plan_react.models import PlanReactRequest, PlanReactConfiguration
from src.reasoning.plan_react.process import PlanReactCoordinator
from src.context.context_assembler import ContextAssembler


@pytest.mark.asyncio
async def test_plan_react_returns_result_within_budget():
    kernel = Kernel()
    coordinator = PlanReactCoordinator(kernel=kernel, config=PlanReactConfiguration())

    request = PlanReactRequest(task="Map delivery timeline and risks.", step_budget=2)
    result = await coordinator.run(request)

    assert result.task == request.task
    assert result.steps_executed <= request.step_budget
    assert result.final_response
    assert result.plan.plan


@pytest.mark.asyncio
async def test_plan_react_flags_extension_when_budget_exhausted():
    kernel = Kernel()
    coordinator = PlanReactCoordinator(kernel=kernel, config=PlanReactConfiguration())

    request = PlanReactRequest(
        task="Investigate issue; propose fix; publish notes.",
        step_budget=1,
        allow_step_extension=True,
    )

    result = await coordinator.run(request)

    assert result.extension_requested is True
    assert result.extension_message


@pytest.mark.asyncio
async def test_plan_react_accepts_context():
    kernel = Kernel()
    coordinator = PlanReactCoordinator(kernel=kernel, config=PlanReactConfiguration())

    assembler = ContextAssembler()
    assembler.add_section("Runbook", "Check interface status", priority=5)
    context = assembler.build()

    request = PlanReactRequest(task="Investigate network latency", step_budget=2)
    result = await coordinator.run(request, context=context)

    assert "Runbook" in result.plan.rationale
