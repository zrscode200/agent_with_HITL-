"""Enhanced two-phase planner with tool-aware tactical planning."""

from __future__ import annotations

import json
import logging
import time
from typing import Dict, List, Optional

from pydantic import ValidationError
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.chat_completion_client_base import ChatCompletionClientBase
from semantic_kernel.functions.kernel_function_decorator import kernel_function
from semantic_kernel.processes.kernel_process.kernel_process_step import KernelProcessStep
from semantic_kernel.processes.kernel_process.kernel_process_step_state import KernelProcessStepState

from src.reasoning.plan_react.models import (
    PlanItem,
    PlanReactPlan,
    PlanReactPlannerState,
    PlanReactRequest,
    StepStatus,
    StrategicPlan,
    StrategicPlanItem,
)
from src.reasoning.plan_react.tool_mapper import StrategicStep, ToolMapper, ToolMapping
from src.plugins.tooling_metadata import RiskLevel, ToolDefinition
from src.policies.approval_service import ApprovalRequest, ApprovalService
from src.policies.policy_models import ApprovalType
from src.observability.feedback_store import FeedbackStore
from src.observability.telemetry_service import TelemetryService
from src.plugins.plugin_suggestions import PluginSuggestionQueue


class EnhancedPlanReactPlannerStep(KernelProcessStep[PlanReactPlannerState]):
    """Two-phase planner: strategic (tool-agnostic) → tactical (tool-aware)."""

    def __init__(
        self,
        kernel: Kernel | None = None,
        logger: logging.Logger | None = None,
        approval_service: Optional[ApprovalService] = None,
        feedback_store: Optional[FeedbackStore] = None,
        telemetry: Optional[TelemetryService] = None,
        plugin_suggestions: Optional[PluginSuggestionQueue] = None,
        tool_manifest: Optional[Dict[str, Dict[str, ToolDefinition]]] = None,
    ) -> None:
        super().__init__()
        self._kernel = kernel or Kernel()
        self._logger = logger or logging.getLogger(self.__class__.__name__)
        self._approval_service = approval_service
        self._feedback_store = feedback_store
        self._telemetry = telemetry
        self._plugin_suggestions = plugin_suggestions
        self._tool_manifest = tool_manifest or {}
        self._tool_mapper = ToolMapper(self._kernel, logger, telemetry)

    async def activate(self, state: KernelProcessStepState[PlanReactPlannerState]):
        self.state = state.state or PlanReactPlannerState()
        state.state = self.state

    @kernel_function(name="bootstrap", description="Generate two-phase plan: strategic → tactical")
    async def bootstrap(self, request: PlanReactRequest) -> PlanReactPlan:
        if not request.task.strip():
            raise ValueError("Task cannot be empty")

        # Phase 1: Strategic Planning (tool-agnostic)
        strategic_plan = await self._create_strategic_plan(request)

        # HITL Trigger #1: Strategic review (optional)
        if request.enable_strategic_hitl and self._approval_service:
            strategic_plan = await self._review_strategic_plan_with_human(strategic_plan, request)

        # Phase 2: Tactical Planning (tool-aware)
        tactical_plan = await self._create_tactical_plan(strategic_plan, request)

        self.state.last_plan = tactical_plan
        return tactical_plan

    async def _create_strategic_plan(self, request: PlanReactRequest) -> StrategicPlan:
        """Phase 1: High-level, tool-agnostic planning."""
        if self._has_chat_completion_service():
            try:
                plan = await self._generate_strategic_plan_with_llm(request)
                if plan:
                    return plan
            except Exception as ex:
                self._logger.warning("Strategic planner failed with LLM: %s", ex)

        return self._generate_strategic_plan_heuristically(request)

    async def _generate_strategic_plan_with_llm(self, request: PlanReactRequest) -> Optional[StrategicPlan]:
        """Generate strategic plan using LLM."""
        services = self._kernel.get_services_by_type(ChatCompletionClientBase)
        if not services:
            return None

        service = services[0]
        settings = service.instantiate_prompt_execution_settings()
        prompt = self._strategic_planner_prompt(request)

        response = await service.get_chat_message_content([], settings, prompt=prompt)
        if response is None or not response.content:
            return None

        # Parse JSON response
        try:
            data = json.loads(response.content)
            steps = []
            for step_data in data.get("steps", []):
                steps.append(
                    StrategicPlanItem(
                        step_number=step_data["number"],
                        title=step_data["title"],
                        required_capability=step_data.get("required_capability", "general"),
                        success_criteria=step_data.get("success_criteria", ""),
                        description=step_data.get("description"),
                    )
                )

            return StrategicPlan(
                task=request.task,
                goal=data.get("goal", request.task),
                rationale=data.get("rationale", "Strategic plan generated by LLM"),
                steps=steps,
                context=request.context,
            )
        except (json.JSONDecodeError, KeyError, ValidationError) as ex:
            self._logger.warning("Failed to parse strategic plan JSON: %s", ex)
            return None

    def _generate_strategic_plan_heuristically(self, request: PlanReactRequest) -> StrategicPlan:
        """Fallback: heuristic strategic planning."""
        # Simple sentence tokenization
        sentences = [s.strip() for s in request.task.split(".") if s.strip()]

        steps = []
        for idx, sentence in enumerate(sentences[:5], start=1):
            steps.append(
                StrategicPlanItem(
                    step_number=idx,
                    title=sentence,
                    required_capability="general",
                    success_criteria=f"Address: {sentence}",
                )
            )

        if not steps:
            steps.append(
                StrategicPlanItem(
                    step_number=1,
                    title="Analyze and respond to task",
                    required_capability="general",
                    success_criteria="Provide thoughtful response",
                )
            )

        return StrategicPlan(
            task=request.task,
            goal=request.task,
            rationale="Generated heuristically (no LLM available)",
            steps=steps,
            context=request.context,
        )

    async def _review_strategic_plan_with_human(
        self, plan: StrategicPlan, request: PlanReactRequest
    ) -> StrategicPlan:
        """HITL: Review strategic plan before tactical planning."""
        if not self._approval_service:
            return plan

        approval_req = ApprovalRequest(
            workflow_id="plan-react",
            plugin_name="StrategicPlanner",
            tool_name="review_strategic_plan",
            risk_level=RiskLevel.LOW,
            rationale="Strategic plan ready for review before tactical mapping",
            approval_type=ApprovalType.STRATEGIC_REVIEW,
            phase="strategic",
            planning_context={
                "task": plan.task,
                "goal": plan.goal,
                "step_count": len(plan.steps),
                "plan_summary": plan.to_prompt(),
            },
        )

        start_time = time.perf_counter()
        decision = self._approval_service.request_approval(approval_req)
        duration = time.perf_counter() - start_time

        # Log feedback
        if self._feedback_store:
            self._feedback_store.record(
                workflow_id="plan-react",
                phase="strategic-planning",
                note=decision.reason or "Strategic plan reviewed",
                metadata={"approved": decision.approved, "reviewer": decision.reviewer},
            )

        # Log telemetry
        if self._telemetry:
            self._telemetry.record_planning_approval(
                workflow_id="plan-react",
                phase="strategic",
                approval_type=ApprovalType.STRATEGIC_REVIEW.value,
                approved=decision.approved,
                reviewer=decision.reviewer,
                context={"duration_seconds": duration, "step_count": len(plan.steps)},
            )

        if not decision.approved:
            self._logger.warning("Strategic plan rejected by human reviewer")
            # Could trigger replanning here if needed

        return plan

    async def _create_tactical_plan(
        self, strategic_plan: StrategicPlan, request: PlanReactRequest
    ) -> PlanReactPlan:
        """Phase 2: Map strategic steps to available tools."""
        tactical_items: List[PlanItem] = []

        for strategic_item in strategic_plan.steps:
            # Convert to StrategicStep for mapper
            strategic_step = StrategicStep(
                number=strategic_item.step_number,
                title=strategic_item.title,
                required_capability=strategic_item.required_capability,
                success_criteria=strategic_item.success_criteria,
                description=strategic_item.description,
            )

            # Map to tools
            mapping = self._tool_mapper.map_step_to_tools(strategic_step, self._tool_manifest)

            # Handle mapping result
            if mapping.is_feasible:
                # Successfully mapped
                plan_item = self._create_plan_item_from_mapping(mapping)
                tactical_items.append(plan_item)
            else:
                # Gap detected - HITL intervention
                if request.enable_feasibility_hitl and self._approval_service:
                    resolution = await self._handle_missing_capability(mapping, request)
                    tactical_items.append(resolution)
                else:
                    # No HITL: mark as blocked
                    tactical_items.append(
                        PlanItem(
                            step_number=strategic_item.step_number,
                            title=strategic_item.title,
                            success_criteria=strategic_item.success_criteria,
                            status=StepStatus.BLOCKED,
                            capability=strategic_item.required_capability,
                            mapping_confidence=0.0,
                            mapping_method="none",
                        )
                    )

        return PlanReactPlan(
            task=strategic_plan.task,
            rationale=f"Tactical plan mapped from strategic plan. {strategic_plan.rationale}",
            step_budget=request.step_budget,
            allow_step_extension=request.allow_step_extension,
            plan=tactical_items,
            context=request.context,
            strategic_plan=strategic_plan,
        )

    def _create_plan_item_from_mapping(self, mapping: ToolMapping) -> PlanItem:
        """Create PlanItem from successful tool mapping."""
        # Use first matched tool
        plugin_name, tool_name = mapping.matched_tools[0] if mapping.matched_tools else (None, None)

        return PlanItem(
            step_number=mapping.strategic_step.number,
            title=mapping.strategic_step.title,
            success_criteria=mapping.strategic_step.success_criteria,
            status=StepStatus.READY,
            plugin_name=plugin_name,
            tool_name=tool_name,
            capability=mapping.required_capability,
            mapping_confidence=mapping.confidence,
            mapping_method=mapping.mapping_method,
        )

    async def _handle_missing_capability(
        self, mapping: ToolMapping, request: PlanReactRequest
    ) -> PlanItem:
        """HITL intervention for missing tool capability."""
        if not self._approval_service:
            # Fallback: mark as blocked
            return PlanItem(
                step_number=mapping.strategic_step.number,
                title=mapping.strategic_step.title,
                success_criteria=mapping.strategic_step.success_criteria,
                status=StepStatus.BLOCKED,
                capability=mapping.required_capability,
                mapping_confidence=0.0,
                mapping_method="none",
            )

        # Build approval request
        approval_req = ApprovalRequest(
            workflow_id="plan-react",
            plugin_name="TacticalPlanner",
            tool_name=mapping.required_capability,
            risk_level=self._map_to_risk_level(mapping),
            rationale=f"Step '{mapping.strategic_step.title}' requires {mapping.required_capability} but no tool available.",
            approval_type=ApprovalType.TACTICAL_FEASIBILITY,
            phase="tactical-planning",
            planning_context={
                "strategic_step": mapping.strategic_step.title,
                "required_capability": mapping.required_capability,
                "gap_reason": mapping.gap_reason,
                "suggested_plugin": mapping.suggested_plugin,
                "confidence": mapping.confidence,
            },
        )

        start_time = time.perf_counter()
        decision = self._approval_service.request_approval(approval_req)
        duration = time.perf_counter() - start_time

        # Log feedback
        if self._feedback_store:
            self._feedback_store.record(
                workflow_id="plan-react",
                phase="tactical-planning",
                note=decision.reason or "Gap resolution decision",
                metadata={
                    "step": mapping.strategic_step.title,
                    "capability": mapping.required_capability,
                    "approved": decision.approved,
                    "reviewer": decision.reviewer,
                },
            )

        # Log telemetry
        if self._telemetry:
            self._telemetry.record_planning_approval(
                workflow_id="plan-react",
                phase="tactical",
                approval_type=ApprovalType.TACTICAL_FEASIBILITY.value,
                approved=decision.approved,
                reviewer=decision.reviewer,
                context={
                    "step": mapping.strategic_step.title,
                    "capability": mapping.required_capability,
                    "duration_seconds": duration,
                },
            )

        # Parse human decision from reason
        reason_lower = (decision.reason or "").lower()

        if "skip" in reason_lower:
            status = StepStatus.SKIPPED
        elif "manual" in reason_lower:
            status = StepStatus.MANUAL
        elif "plugin" in reason_lower and mapping.suggested_plugin:
            # Queue plugin suggestion
            if self._plugin_suggestions:
                self._plugin_suggestions.suggest_plugin(
                    plugin_name=mapping.suggested_plugin,
                    capability=mapping.required_capability,
                    workflow_id="plan-react",
                    rationale=f"Needed for step: {mapping.strategic_step.title}",
                )
                self._logger.info(f"Plugin suggestion queued: {mapping.suggested_plugin}")
            status = StepStatus.BLOCKED  # Still blocked until plugin installed
        else:
            status = StepStatus.BLOCKED

        return PlanItem(
            step_number=mapping.strategic_step.number,
            title=mapping.strategic_step.title,
            success_criteria=mapping.strategic_step.success_criteria,
            status=status,
            capability=mapping.required_capability,
            mapping_confidence=0.0,
            mapping_method="manual",
            human_override=decision.reason,
        )

    def _map_to_risk_level(self, mapping: ToolMapping) -> RiskLevel:
        """Map tool mapping confidence to planning risk level."""
        if mapping.suggested_plugin:
            return RiskLevel.HIGH  # Plugin installation = high risk
        elif mapping.confidence < 0.3:
            return RiskLevel.MEDIUM  # Very uncertain mapping
        else:
            return RiskLevel.LOW  # Minor gap

    def _strategic_planner_prompt(self, request: PlanReactRequest) -> str:
        """Prompt for strategic (tool-agnostic) planning."""
        context_text = request.context.get("prompt_context", "")
        hints = "\n".join(f"- {hint}" for hint in request.hints) if request.hints else "- None"

        return f"""You are a strategic planning specialist. Create a high-level plan.

Think about WHAT needs to be done, not HOW (tools will be mapped later).

Task: {request.task}
Context: {context_text}
Hints: {hints}

Output JSON with this structure:
{{
  "goal": "overall objective",
  "rationale": "why this approach",
  "steps": [
    {{
      "number": 1,
      "title": "high-level step description",
      "required_capability": "document_processing | web_access | diagnostics | data_analysis | general",
      "success_criteria": "what success looks like",
      "description": "optional details"
    }}
  ]
}}

Keep steps high-level and capability-focused. Limit to {request.step_budget} steps max.
Return ONLY valid JSON, no other text."""

    def _has_chat_completion_service(self) -> bool:
        services = self._kernel.get_services_by_type(ChatCompletionClientBase)
        return bool(services)


__all__ = ["EnhancedPlanReactPlannerStep"]
