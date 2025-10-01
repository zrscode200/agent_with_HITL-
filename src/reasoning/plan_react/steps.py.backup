"""Custom process steps implementing the deterministic Plan→ReAct workflow."""

from __future__ import annotations

import json
import logging
import re
from typing import Iterable, List

from pydantic import ValidationError
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.chat_completion_client_base import ChatCompletionClientBase
from semantic_kernel.functions.kernel_function_decorator import kernel_function
from semantic_kernel.processes.kernel_process.kernel_process_step import KernelProcessStep
from semantic_kernel.processes.kernel_process.kernel_process_step_state import KernelProcessStepState

from src.reasoning.plan_react.models import (
    ExecutionTrace,
    PlanItem,
    PlanReactExecutorState,
    PlanReactPlan,
    PlanReactPlannerState,
    PlanReactRequest,
    PlanReactResult,
)


class PlanReactPlannerStep(KernelProcessStep[PlanReactPlannerState]):
    """Planning step that drafts an initial strategy for the agent."""

    def __init__(self, kernel: Kernel | None = None, logger: logging.Logger | None = None) -> None:
        super().__init__()
        self._kernel = kernel or Kernel()
        self._logger = logger or logging.getLogger(self.__class__.__name__)

    async def activate(self, state: KernelProcessStepState[PlanReactPlannerState]):
        self.state = state.state or PlanReactPlannerState()
        state.state = self.state

    @kernel_function(name="bootstrap", description="Generate a structured plan for the incoming task")
    async def bootstrap(self, request: PlanReactRequest) -> PlanReactPlan:
        if not request.task.strip():
            raise ValueError("Task cannot be empty")

        plan = await self._generate_plan(request)
        self.state.last_plan = plan
        return plan

    async def _generate_plan(self, request: PlanReactRequest) -> PlanReactPlan:
        if self._has_chat_completion_service():
            try:
                plan = await self._generate_plan_with_llm(request)
                if plan:
                    return plan
            except Exception as ex:  # pragma: no cover - defensive for unsupported runtimes
                self._logger.warning("Planner failed to use chat completion service: %s", ex)

        return self._generate_plan_heuristically(request)

    async def _generate_plan_with_llm(self, request: PlanReactRequest) -> PlanReactPlan | None:
        services = self._kernel.get_services_by_type(ChatCompletionClientBase)
        if not services:
            return None

        service = services[0]
        settings = service.instantiate_prompt_execution_settings()
        prompt = self._planner_prompt(request)

        response = await service.get_chat_message_content([], settings, prompt=prompt)
        if response is None or not response.content:
            return None

        structured = self._parse_plan_from_json(response.content)
        if structured:
            structured.context = request.context
            structured.step_budget = request.step_budget
            structured.allow_step_extension = request.allow_step_extension
            structured.task = request.task
            return structured

        return None

    def _generate_plan_heuristically(self, request: PlanReactRequest) -> PlanReactPlan:
        sentences = self._tokenize_sentences(request.task)
        plan_items: List[PlanItem] = []
        for idx, sentence in enumerate(sentences, start=1):
            plan_items.append(
                PlanItem(
                    step_number=idx,
                    title=sentence,
                    success_criteria=f"Answer or resolve: {sentence}",
                )
            )

        if not plan_items:
            plan_items.append(
                PlanItem(
                    step_number=1,
                    title="Analyze request",
                    success_criteria="Identify the key requirement in the task description.",
                )
            )

        context_snippet = request.context.get("prompt_context", "")

        plan = PlanReactPlan(
            task=request.task,
            rationale="Generated heuristically due to missing chat completion service.",
            step_budget=request.step_budget,
            allow_step_extension=request.allow_step_extension,
            plan=plan_items,
            context=request.context,
        )
        if context_snippet:
            plan.rationale += " Context provided: " + context_snippet[:200]
        return plan

    def _parse_plan_from_json(self, content: str) -> PlanReactPlan | None:
        try:
            data = json.loads(content)
            return PlanReactPlan.model_validate(data)
        except (json.JSONDecodeError, ValidationError):
            return None

    def _tokenize_sentences(self, text: str) -> List[str]:
        candidates = [segment.strip() for segment in re.split(r"[\.;\n]+", text) if segment.strip()]
        return candidates[:10] if candidates else []

    def _has_chat_completion_service(self) -> bool:
        services = self._kernel.get_services_by_type(ChatCompletionClientBase)
        return bool(services)

    def _planner_prompt(self, request: PlanReactRequest) -> str:
        hints = "\n".join(f"- {hint}" for hint in request.hints) if request.hints else "- None provided"
        context_text = request.context.get("prompt_context")
        parts = [
            "You are a planning specialist. Craft a concise plan expressed as JSON with the keys:\n"
            "task (string), rationale (string), step_budget (int), allow_step_extension (bool),"
            " plan (list of items with step_number, title, success_criteria).\n"
            "The plan must respect the provided step budget.\n"
            f"Task: {request.task}\n"
            f"Step budget: {request.step_budget}\n"
            f"Hints:\n{hints}\n"
        ]
        if context_text:
            parts.append("Context:\n" + context_text)
        parts.append("Return only valid JSON.")
        return "".join(parts)


class PlanReactExecutorStep(KernelProcessStep[PlanReactExecutorState]):
    """Executor step that performs deterministic reasoning-action-observation loops."""

    def __init__(self, kernel: Kernel | None = None, logger: logging.Logger | None = None) -> None:
        super().__init__()
        self._kernel = kernel or Kernel()
        self._logger = logger or logging.getLogger(self.__class__.__name__)

    async def activate(self, state: KernelProcessStepState[PlanReactExecutorState]):
        self.state = state.state or PlanReactExecutorState()
        state.state = self.state

    @kernel_function(name="execute_plan", description="Execute the supplied plan using a bounded ReAct loop")
    async def execute_plan(self, plan: PlanReactPlan) -> PlanReactResult:
        traces: List[ExecutionTrace] = []
        remaining_budget = int(plan.step_budget)

        for item in plan.plan:
            if remaining_budget <= 0:
                break

            thought = f"Evaluate next step {item.step_number}: {item.title}"
            action = f"Act on: {item.title}"
            observation = self._simulate_observation(item, plan.context)

            traces.append(
                ExecutionTrace(
                    sequence=len(traces) + 1,
                    thought=thought,
                    action=action,
                    observation=observation,
                )
            )
            remaining_budget -= 1

        extension_requested = bool(remaining_budget <= 0 and len(traces) < len(plan.plan) and plan.allow_step_extension)
        extension_message = None
        if extension_requested:
            extension_message = (
                "Step budget exhausted before all plan items were executed. "
                "Request human confirmation to extend the limit."
            )

        final_response = self._synthesize_response(plan.task, traces, plan.context)

        result = PlanReactResult(
            task=plan.task,
            final_response=final_response,
            steps_executed=len(traces),
            plan=plan,
            traces=traces,
            extension_requested=extension_requested,
            extension_message=extension_message,
        )

        self.state.last_result = result
        self.state.remaining_budget = remaining_budget
        return result

    def _simulate_observation(self, item: PlanItem, context: dict | None) -> str:
        context_hint = "" if not context else f" using context keys {', '.join(context.keys())}"
        return f"Completed analytical pass for '{item.title}'{context_hint}."

    def _synthesize_response(
        self,
        task: str,
        traces: Iterable[ExecutionTrace],
        context: dict | None,
    ) -> str:
        if not traces:
            return f"No actions executed for task: {task}."

        highlights = ", ".join(trace.observation for trace in traces)
        if context:
            return f"Task '{task}' addressed with context support; observations: {highlights}."
        return f"Task '{task}' addressed; observations: {highlights}."
