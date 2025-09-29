"""Coordinator that assembles and executes the Plan→ReAct process."""

from __future__ import annotations

import contextlib
import logging
import time
from typing import Optional

from semantic_kernel import Kernel
from semantic_kernel.processes import ProcessBuilder
from semantic_kernel.processes.kernel_process.kernel_process import KernelProcess
from semantic_kernel.processes.kernel_process.kernel_process_event import KernelProcessEvent
from semantic_kernel.processes.local_runtime.local_process import LocalProcess

from src.observability.telemetry_service import TelemetryService
from src.reasoning.plan_react.models import (
    PlanReactConfiguration,
    PlanReactExecutorState,
    PlanReactRequest,
    PlanReactResult,
)
from src.reasoning.plan_react.steps import PlanReactExecutorStep, PlanReactPlannerStep

_START_EVENT_ID = "PlanReact.Start"
_PLANNER_NAME = "Planner"
_EXECUTOR_NAME = "Executor"


class PlanReactCoordinator:
    """Public facade for invoking the deterministic Plan→ReAct pipeline."""

    WORKFLOW_ID = "plan-react"


    def __init__(
        self,
        *,
        kernel: Kernel,
        config: PlanReactConfiguration,
        telemetry_service: Optional[TelemetryService] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._kernel = kernel
        self._config = config
        self._telemetry = telemetry_service
        self._logger = logger or logging.getLogger(self.__class__.__name__)

        self._builder = self._compose_process()

    async def run(self, request: PlanReactRequest | str, step_budget: Optional[int] = None) -> PlanReactResult:
        """Execute the pipeline for the supplied request."""
        normalized_request = self._normalize_request(request, step_budget)

        kernel_process = self._builder.build()
        KernelProcess.model_rebuild()
        LocalProcess.model_rebuild(_types_namespace={"KernelProcess": KernelProcess})
        local_process = LocalProcess(
            process=kernel_process,
            kernel=self._kernel,
            factories=self._builder.factories,
            max_supersteps=min(self._config.max_supersteps, normalized_request.step_budget * 4),
        )

        start_event = KernelProcessEvent(id=_START_EVENT_ID, data=normalized_request)

        activity = None
        if self._telemetry:
            activity = self._telemetry.start_activity(
                "PlanReactCoordinator.run",
                {
                    "task": normalized_request.task,
                    "step_budget": normalized_request.step_budget,
                    "allow_extension": normalized_request.allow_step_extension,
                },
            )

        with activity or contextlib.nullcontext():
            timer = time.perf_counter()
            await local_process.run_once(start_event)
            duration = time.perf_counter() - timer

        result = self._extract_result(local_process)
        if self._telemetry:
            self._telemetry.record_agent_execution(
                agent_name="PlanReactCoordinator",
                duration_seconds=duration,
                success=True,
                tags={
                    "steps.executed": result.steps_executed,
                    "step_budget": normalized_request.step_budget,
                    "extension_requested": str(result.extension_requested).lower(),
                },
            )

        return result

    def _compose_process(self) -> ProcessBuilder:
        builder = ProcessBuilder(name="PlanReactPipeline", kernel=self._kernel)

        planner = builder.add_step(
            PlanReactPlannerStep,
            name=_PLANNER_NAME,
            factory_function=lambda: PlanReactPlannerStep(
                kernel=self._kernel,
                logger=self._logger.getChild("Planner"),
            ),
            kernel=self._kernel,
        )

        executor = builder.add_step(
            PlanReactExecutorStep,
            name=_EXECUTOR_NAME,
            factory_function=lambda: PlanReactExecutorStep(
                kernel=self._kernel,
                logger=self._logger.getChild("Executor"),
            ),
            kernel=self._kernel,
        )

        builder.on_input_event(_START_EVENT_ID).send_event_to(
            planner,
            function_name="bootstrap",
            parameter_name="request",
        )

        planner.on_event("bootstrap.OnResult").send_event_to(
            executor,
            function_name="execute_plan",
            parameter_name="plan",
        )

        executor.on_event("execute_plan.OnResult").stop_process()

        return builder

    def _normalize_request(
        self,
        request: PlanReactRequest | str,
        step_budget: Optional[int],
    ) -> PlanReactRequest:
        if isinstance(request, PlanReactRequest):
            if step_budget:
                return request.model_copy(update={"step_budget": step_budget})
            return request

        text = request.strip()
        budget = step_budget or self._config.default_step_budget
        return PlanReactRequest(task=text, step_budget=budget)

    def _extract_result(self, process: LocalProcess) -> PlanReactResult:
        executor_state = self._find_executor_state(process)
        if not executor_state.last_result:
            raise RuntimeError("Executor step did not produce a result")
        return executor_state.last_result

    def _find_executor_state(self, process: LocalProcess) -> PlanReactExecutorState:
        for step in process.steps:
            if step.name == _EXECUTOR_NAME:
                state = step.step_state.state
                if isinstance(state, PlanReactExecutorState):
                    return state
        raise RuntimeError("Executor step state not found")


__all__ = ["PlanReactCoordinator", "PlanReactConfiguration"]
