"""Coordinator that assembles and executes the Plan→ReAct process."""

from __future__ import annotations

import contextlib
import logging
import time
from typing import Dict, Optional

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
    ReplanContext,
)
from src.context.context_assembler import AssembledContext
from src.context.workflow_context import WorkflowContextManager
from src.observability.feedback_store import FeedbackStore
from src.reasoning.plan_react.steps import PlanReactExecutorStep, PlanReactPlannerStep
from src.reasoning.plan_react.steps_enhanced import EnhancedPlanReactPlannerStep
from src.reasoning.plan_react.steps_reactive import ReactivePlanReactExecutorStep
from src.policies.approval_service import ApprovalService
from src.plugins.plugin_suggestions import PluginSuggestionQueue
from src.plugins.tooling_metadata import ToolDefinition
from src.runtime.tool_gateway import ToolGateway

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
        context_manager: Optional[WorkflowContextManager] = None,
        feedback_store: Optional[FeedbackStore] = None,
        logger: Optional[logging.Logger] = None,
        approval_service: Optional[ApprovalService] = None,  # NEW
        plugin_suggestions: Optional[PluginSuggestionQueue] = None,  # NEW
        tool_manifest: Optional[Dict[str, Dict[str, ToolDefinition]]] = None,  # NEW
        use_enhanced_planner: bool = False,  # NEW: toggle for two-phase planning
        use_reactive_executor: bool = False,  # NEW: toggle for ReAct executor
        tool_gateway: Optional[ToolGateway] = None,  # NEW: needed for execution approvals
    ) -> None:
        self._kernel = kernel
        self._config = config
        self._telemetry = telemetry_service
        self._logger = logger or logging.getLogger(self.__class__.__name__)
        self._context_manager = context_manager
        self._feedback_store = feedback_store
        self._approval_service = approval_service
        self._plugin_suggestions = plugin_suggestions
        self._tool_manifest = tool_manifest
        self._use_enhanced_planner = use_enhanced_planner
        self._use_reactive_executor = use_reactive_executor
        self._tool_gateway = tool_gateway

        self._builder = self._compose_process()

    async def run(
        self,
        request: PlanReactRequest | str,
        *,
        step_budget: Optional[int] = None,
        context: Optional[AssembledContext] = None,
    ) -> PlanReactResult:
        """Execute the pipeline with automatic re-planning on critical divergence."""
        if context is None and self._context_manager is not None:
            context = self._context_manager.assemble(self.WORKFLOW_ID)

        normalized_request = self._normalize_request(request, step_budget)
        if context is not None:
            normalized_request.context = dict(normalized_request.context)
            normalized_request.context["prompt_context"] = context.as_prompt()
            normalized_request.context["prompt_profile"] = context.profile.name

        # Re-planning loop
        max_replans = self._config.max_replans if self._config.enable_auto_replan else 0
        replan_count = 0
        original_request = normalized_request

        while replan_count <= max_replans:
            activity = None
            if self._telemetry:
                activity = self._telemetry.start_activity(
                    f"PlanReactCoordinator.run.attempt_{replan_count}",
                    {
                        "task": normalized_request.task,
                        "step_budget": normalized_request.step_budget,
                        "replan_attempt": replan_count,
                    },
                )

            with activity or contextlib.nullcontext():
                timer = time.perf_counter()
                result = await self._execute_process(normalized_request)
                duration = time.perf_counter() - timer

            # Log execution
            if self._telemetry:
                self._telemetry.record_agent_execution(
                    agent_name="PlanReactCoordinator",
                    duration_seconds=duration,
                    success=not result.replan_requested,
                    tags={
                        "steps.executed": result.steps_executed,
                        "step_budget": normalized_request.step_budget,
                        "replan_attempt": str(replan_count),
                        "replan_requested": str(result.replan_requested).lower(),
                    },
                )

            # Check if re-planning needed
            if not result.replan_requested:
                # Success! Return result
                return result

            # Re-planning needed
            self._logger.warning(
                f"Re-planning requested (attempt {replan_count + 1}/{max_replans + 1}): "
                f"{result.replan_context.divergence.reason if result.replan_context else 'unknown'}"
            )

            # Check if we can replan
            if replan_count >= max_replans:
                self._logger.error(f"Max re-planning attempts ({max_replans}) exceeded")
                # Record telemetry for max replans exceeded
                if self._telemetry:
                    self._telemetry.record_agent_execution(
                        agent_name="PlanReactCoordinator.MaxReplansExceeded",
                        duration_seconds=0.0,
                        success=False,
                        tags={"replan_count": str(replan_count)},
                    )
                return result  # Return with replan_requested=True

            # Request HITL approval for re-planning
            if not await self._request_replan_approval(result.replan_context):
                self._logger.info("Re-planning declined by human")
                return result  # Return with replan_requested=True

            # Prepare new request with enriched context
            normalized_request = self._prepare_replan_request(original_request, result.replan_context)
            replan_count += 1

            # Log re-planning event
            if self._telemetry:
                self._telemetry.record_agent_execution(
                    agent_name="PlanReactCoordinator.Replan",
                    duration_seconds=0.0,
                    success=True,
                    tags={
                        "replan_number": str(replan_count),
                        "divergence_reason": result.replan_context.divergence.reason,
                        "divergence_severity": result.replan_context.divergence.severity.value,
                    },
                )

        # Should never reach here
        return result

    def _compose_process(self) -> ProcessBuilder:
        builder = ProcessBuilder(name="PlanReactPipeline", kernel=self._kernel)

        # Choose planner type based on configuration
        if self._use_enhanced_planner:
            planner = builder.add_step(
                EnhancedPlanReactPlannerStep,
                name=_PLANNER_NAME,
                factory_function=lambda: EnhancedPlanReactPlannerStep(
                    kernel=self._kernel,
                    logger=self._logger.getChild("EnhancedPlanner"),
                    approval_service=self._approval_service,
                    feedback_store=self._feedback_store,
                    telemetry=self._telemetry,
                    plugin_suggestions=self._plugin_suggestions,
                    tool_manifest=self._tool_manifest,
                ),
                kernel=self._kernel,
            )
        else:
            planner = builder.add_step(
                PlanReactPlannerStep,
                name=_PLANNER_NAME,
                factory_function=lambda: PlanReactPlannerStep(
                    kernel=self._kernel,
                    logger=self._logger.getChild("Planner"),
                ),
                kernel=self._kernel,
            )

        if self._use_reactive_executor:
            executor = builder.add_step(
                ReactivePlanReactExecutorStep,
                name=_EXECUTOR_NAME,
                factory_function=lambda: ReactivePlanReactExecutorStep(
                    kernel=self._kernel,
                    logger=self._logger.getChild("ReactiveExecutor"),
                    tool_gateway=self._tool_gateway,
                    approval_service=self._approval_service,
                    telemetry=self._telemetry,
                    feedback_store=self._feedback_store,
                    context_manager=self._context_manager,
                ),
                kernel=self._kernel,
            )
        else:
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

    def register_pre_run_note(self, note: str) -> None:
        if self._context_manager:
            self._context_manager.register_human_note(self.WORKFLOW_ID, "pre", note)
        if self._feedback_store:
            self._feedback_store.record(
                workflow_id=self.WORKFLOW_ID,
                phase="pre",
                note=note,
                metadata={},
            )

    def register_post_run_feedback(self, note: str) -> None:
        if self._context_manager:
            self._context_manager.register_human_note(self.WORKFLOW_ID, "post", note)
        if self._feedback_store:
            self._feedback_store.record(
                workflow_id=self.WORKFLOW_ID,
                phase="post",
                note=note,
                metadata={},
            )

    async def _execute_process(self, request: PlanReactRequest) -> PlanReactResult:
        """Execute a single plan→execute cycle."""
        kernel_process = self._builder.build()
        KernelProcess.model_rebuild()
        LocalProcess.model_rebuild(_types_namespace={"KernelProcess": KernelProcess})
        local_process = LocalProcess(
            process=kernel_process,
            kernel=self._kernel,
            factories=self._builder.factories,
            max_supersteps=min(self._config.max_supersteps, request.step_budget * 4),
        )

        start_event = KernelProcessEvent(id=_START_EVENT_ID, data=request)
        await local_process.run_once(start_event)

        result = self._extract_result(local_process)
        return result

    async def _request_replan_approval(self, replan_context: Optional[ReplanContext]) -> bool:
        """Request HITL approval for re-planning."""
        if not self._approval_service or not replan_context:
            return False

        from src.policies.approval_service import ApprovalRequest
        from src.plugins.tooling_metadata import RiskLevel
        from src.policies.policy_models import ApprovalType

        approval_req = ApprovalRequest(
            workflow_id=self.WORKFLOW_ID,
            plugin_name="PlanReactCoordinator",
            tool_name="replan",
            risk_level=RiskLevel.HIGH,
            rationale=f"Execution diverged: {replan_context.divergence.reason}",
            approval_type=ApprovalType.STRATEGIC_REVIEW,
            phase="execution",
            planning_context={
                "original_task": replan_context.original_plan.task,
                "divergence": {
                    "severity": replan_context.divergence.severity.value,
                    "reason": replan_context.divergence.reason,
                    "step": replan_context.divergence.step_number,
                    "observed": replan_context.divergence.observed_state[:200],
                    "expected": replan_context.divergence.expected_state[:200],
                },
                "steps_completed": len(replan_context.completed_steps),
                "steps_total": len(replan_context.original_plan.plan),
                "lessons_learned": replan_context.lessons_learned,
            },
        )

        decision = self._approval_service.request_approval(approval_req)

        # Log feedback
        if self._feedback_store:
            self._feedback_store.record(
                workflow_id=self.WORKFLOW_ID,
                phase="replan-approval",
                note=decision.reason or "Re-planning decision",
                metadata={
                    "approved": decision.approved,
                    "reviewer": decision.reviewer,
                    "divergence": replan_context.divergence.reason,
                },
            )

        return decision.approved

    def _prepare_replan_request(
        self, original_request: PlanReactRequest, replan_context: ReplanContext
    ) -> PlanReactRequest:
        """Build enriched request for re-planning."""
        # Enrich context with execution history
        enriched_context = dict(original_request.context)
        enriched_context["replan_context"] = {
            "original_plan_rationale": replan_context.original_plan.rationale,
            "execution_summary": [
                {
                    "step": entry["title"],
                    "observation": entry["observation"][:200],
                    "divergence": entry.get("divergence"),
                }
                for entry in replan_context.scratchpad
            ],
            "divergence": {
                "severity": replan_context.divergence.severity.value,
                "reason": replan_context.divergence.reason,
                "observed": replan_context.divergence.observed_state[:200],
                "expected": replan_context.divergence.expected_state[:200],
            },
            "lessons_learned": replan_context.lessons_learned,
            "completed_steps": replan_context.completed_steps,
        }

        # Create new request with enriched context
        return PlanReactRequest(
            task=original_request.task,
            step_budget=replan_context.remaining_budget + 2,  # Give a bit more budget
            allow_step_extension=original_request.allow_step_extension,
            context=enriched_context,
            hints=original_request.hints
            + [
                "Previous plan failed due to: " + replan_context.divergence.reason,
                "Lessons learned: " + "; ".join(replan_context.lessons_learned[:3]),
            ],
            enable_strategic_hitl=original_request.enable_strategic_hitl,
            enable_feasibility_hitl=original_request.enable_feasibility_hitl,
            auto_install_plugins=original_request.auto_install_plugins,
        )


__all__ = ["PlanReactCoordinator", "PlanReactConfiguration"]
