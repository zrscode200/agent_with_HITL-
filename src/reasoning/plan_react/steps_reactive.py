"""Reactive executor implementing ReAct-style reasoning-action-observation loops."""

from __future__ import annotations

import json
import logging
from collections import deque
from typing import Any, Deque, Dict, List, Optional

from pydantic import ValidationError
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.chat_completion_client_base import ChatCompletionClientBase
from semantic_kernel.functions.kernel_function_decorator import kernel_function
from semantic_kernel.processes.kernel_process.kernel_process_step import KernelProcessStep
from semantic_kernel.processes.kernel_process.kernel_process_step_state import KernelProcessStepState

from src.context.workflow_context import WorkflowContextManager
from src.observability.feedback_store import FeedbackStore
from src.observability.telemetry_service import TelemetryService
from src.policies.approval_service import ApprovalRequest, ApprovalService
from src.policies.policy_models import ApprovalType
from src.plugins.tooling_metadata import RiskLevel
from src.runtime.tool_gateway import ToolExecutionContext, ToolGateway
from src.reasoning.plan_react.models import (
    ActionDecision,
    ActionType,
    DivergenceSignal,
    DivergenceSeverity,
    ExecutionTrace,
    PlanItem,
    PlanReactExecutorState,
    PlanReactPlan,
    PlanReactResult,
    ReplanContext,
    StepStatus,
)


class ReactivePlanReactExecutorStep(KernelProcessStep[PlanReactExecutorState]):
    """Executor that adapts each action based on prior observations (ReAct loop)."""

    def __init__(
        self,
        kernel: Optional[Kernel] = None,
        *,
        logger: Optional[logging.Logger] = None,
        tool_gateway: Optional[ToolGateway] = None,
        approval_service: Optional[ApprovalService] = None,
        telemetry: Optional[TelemetryService] = None,
        feedback_store: Optional[FeedbackStore] = None,
        context_manager: Optional[WorkflowContextManager] = None,
    ) -> None:
        super().__init__()
        self._kernel = kernel or Kernel()
        self._logger = logger or logging.getLogger(self.__class__.__name__)
        self._tool_gateway = tool_gateway
        self._approval_service = approval_service
        self._telemetry = telemetry
        self._feedback_store = feedback_store
        self._context_manager = context_manager

    async def activate(self, state: KernelProcessStepState[PlanReactExecutorState]):
        self.state = state.state or PlanReactExecutorState()
        state.state = self.state

    @kernel_function(name="execute_plan", description="Execute a tactical plan with adaptive ReAct reasoning")
    async def execute_plan(self, plan: PlanReactPlan) -> PlanReactResult:
        queue: Deque[PlanItem] = deque(plan.plan)
        traces: List[ExecutionTrace] = []
        scratchpad: List[Dict[str, str]] = []

        remaining_budget = int(plan.step_budget)
        processed: set[int] = set()

        authorized_tools: Dict[str, ToolExecutionContext] = {}
        if self._tool_gateway:
            authorized_tools = self._tool_gateway.list_authorized_tools("plan-react")

        while remaining_budget > 0 and len(processed) < len(plan.plan):
            # Check early termination
            if self._should_terminate_early(plan.task, traces, scratchpad):
                self._logger.info("Task goal appears achieved. Terminating early.")
                break

            item = self._select_next_item(queue, processed)
            if item is None:
                break

            # THINK: LLM-driven reasoning about current state
            thought = await self._llm_reason(item, scratchpad, plan.context, plan.task)

            # ACT: LLM decides next action with parameters (unified call)
            action_decision = await self._llm_decide_action_with_params(
                thought, item, authorized_tools, scratchpad, plan.context
            )

            # Handle action decision
            if action_decision.action_type == ActionType.TERMINATE:
                self._logger.info(f"LLM decided to terminate: {action_decision.rationale}")
                trace = ExecutionTrace(
                    sequence=len(traces) + 1,
                    thought=thought,
                    action="TERMINATE: " + action_decision.rationale,
                    observation="Task completed successfully",
                    action_decision=action_decision,
                )
                traces.append(trace)
                break

            elif action_decision.action_type == ActionType.SKIP_STEP:
                self._logger.info(f"LLM decided to skip step {item.step_number}: {action_decision.rationale}")
                observation = f"Step skipped by LLM: {action_decision.rationale}"

            elif action_decision.action_type == ActionType.REQUEST_REPLAN:
                self._logger.warning(f"LLM requested re-planning: {action_decision.rationale}")
                # Create divergence signal from LLM decision
                divergence = DivergenceSignal(
                    severity=DivergenceSeverity.CRITICAL,
                    step_number=item.step_number,
                    reason=f"LLM requested re-planning: {action_decision.rationale}",
                    observed_state=scratchpad[-1]["observation"] if scratchpad else "N/A",
                    expected_state=item.success_criteria,
                    recommendation=ActionType.REQUEST_REPLAN,
                    context={"llm_rationale": action_decision.rationale},
                )

                # Package replan context
                replan_ctx = self._build_replan_context(
                    plan, traces, scratchpad, divergence, processed, remaining_budget
                )

                # Return with replan request
                result = PlanReactResult(
                    task=plan.task,
                    final_response=f"LLM requested re-planning: {action_decision.rationale}",
                    steps_executed=len(traces),
                    plan=plan,
                    traces=traces,
                    extension_requested=False,
                    replan_requested=True,
                    replan_context=replan_ctx,
                )
                self.state.last_result = result
                self.state.remaining_budget = remaining_budget
                self.state.scratchpad = scratchpad
                return result

            else:  # EXECUTE_TOOL
                observation = await self._execute_item_with_decision(
                    item, plan, scratchpad, authorized_tools, action_decision
                )

            # OBSERVE: Create trace
            trace = ExecutionTrace(
                sequence=len(traces) + 1,
                thought=thought,
                action=self._describe_action_decision(action_decision, item),
                observation=observation,
                action_decision=action_decision,
            )

            # Detect divergence
            divergence = self._detect_divergence(item, observation, action_decision, scratchpad)
            if divergence:
                trace.divergence = divergence
                self._logger.warning(
                    f"Divergence detected (severity={divergence.severity.value}): {divergence.reason}"
                )

                # Log divergence telemetry
                if self._telemetry:
                    self._telemetry.record_agent_execution(
                        agent_name="ReactivePlanReactExecutorStep.Divergence",
                        duration_seconds=0.0,
                        success=False,
                        tags={
                            "severity": divergence.severity.value,
                            "step": str(item.step_number),
                            "recommendation": divergence.recommendation.value,
                        },
                    )

                # Handle critical divergence
                if divergence.severity == DivergenceSeverity.CRITICAL:
                    self._logger.error(f"Critical divergence detected: {divergence.reason}")
                    # Package context for coordinator-level re-planning
                    replan_ctx = self._build_replan_context(
                        plan, traces, scratchpad, divergence, processed, remaining_budget
                    )

                    # Return early with replan request
                    result = PlanReactResult(
                        task=plan.task,
                        final_response=f"Execution halted due to critical divergence: {divergence.reason}",
                        steps_executed=len(traces),
                        plan=plan,
                        traces=traces,
                        extension_requested=False,
                        replan_requested=True,
                        replan_context=replan_ctx,
                    )
                    self.state.last_result = result
                    self.state.remaining_budget = remaining_budget
                    self.state.scratchpad = scratchpad
                    return result

            traces.append(trace)

            scratchpad.append(
                {
                    "title": item.title,
                    "status": item.status.value,
                    "observation": observation,
                    "divergence": divergence.reason if divergence else None,
                }
            )

            processed.add(item.step_number)
            remaining_budget -= 1

            # Allow dynamic extension
            if not queue:
                self._refresh_queue(plan.plan, processed, queue)

        extension_requested = bool(remaining_budget <= 0 and len(processed) < len(plan.plan) and plan.allow_step_extension)
        extension_message = None
        if extension_requested and self._approval_service:
            extension_message = await self._request_extension(plan)

        final_response = self._synthesise_response(plan.task, traces, scratchpad)

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
        self.state.scratchpad = scratchpad
        return result

    def _select_next_item(
        self,
        queue: Deque[PlanItem],
        processed: set[int],
    ) -> Optional[PlanItem]:
        while queue:
            candidate = queue.popleft()
            if candidate.step_number in processed:
                continue
            if candidate.status == StepStatus.READY:
                return candidate
            if candidate.status in {StepStatus.MANUAL, StepStatus.BLOCKED, StepStatus.SKIPPED, StepStatus.NEEDS_DATA}:
                return candidate
        return None

    def _refresh_queue(
        self,
        plan_items: List[PlanItem],
        processed: set[int],
        queue: Deque[PlanItem],
    ) -> None:
        for item in plan_items:
            if item.step_number not in processed:
                queue.append(item)

    def _generate_thought(self, item: PlanItem, scratchpad: List[Dict[str, str]]) -> str:
        if not scratchpad:
            return f"Starting with step {item.step_number}: {item.title}"
        last_obs = scratchpad[-1]["observation"]
        return (
            f"After observing '{last_obs}', evaluate next step {item.step_number}: {item.title}"
        )

    def _describe_action(self, item: PlanItem) -> str:
        if item.status == StepStatus.READY and item.plugin_name and item.tool_name:
            return f"Invoke {item.plugin_name}.{item.tool_name}"
        if item.status == StepStatus.MANUAL:
            return f"Escalate for manual execution: {item.title}"
        if item.status == StepStatus.BLOCKED:
            return f"Blocker encountered: {item.title}"
        if item.status == StepStatus.NEEDS_DATA:
            return f"Request runtime data for: {item.title}"
        if item.status == StepStatus.SKIPPED:
            return f"Skip step per human decision: {item.title}"
        return item.title

    def _describe_action_decision(self, action_decision: ActionDecision, item: PlanItem) -> str:
        """Describe action decision for trace."""
        if action_decision.action_type == ActionType.EXECUTE_TOOL:
            return f"Execute tool: {action_decision.tool_name or 'unknown'} ({action_decision.rationale})"
        elif action_decision.action_type == ActionType.SKIP_STEP:
            return f"Skip step: {item.title} ({action_decision.rationale})"
        elif action_decision.action_type == ActionType.TERMINATE:
            return f"Terminate execution ({action_decision.rationale})"
        elif action_decision.action_type == ActionType.REQUEST_REPLAN:
            return f"Request re-planning ({action_decision.rationale})"
        return f"Action: {action_decision.action_type.value}"

    async def _execute_item_with_decision(
        self,
        item: PlanItem,
        plan: PlanReactPlan,
        scratchpad: List[Dict[str, str]],
        authorized_tools: Dict[str, ToolExecutionContext],
        action_decision: ActionDecision,
    ) -> str:
        """Execute item based on action decision."""
        if item.status == StepStatus.READY and item.plugin_name and item.tool_name and self._tool_gateway:
            observation = await self._execute_ready_item(
                item, authorized_tools, action_decision, scratchpad, plan.context
            )
        elif item.status == StepStatus.MANUAL:
            observation = f"Manual execution required for '{item.title}'."
        elif item.status == StepStatus.BLOCKED:
            observation = f"Capability '{item.capability}' missing; step marked blocked."
        elif item.status == StepStatus.SKIPPED:
            observation = f"Step '{item.title}' skipped based on human instruction."
        elif item.status == StepStatus.NEEDS_DATA:
            observation = await self._handle_runtime_data_request(item)
        else:
            observation = f"No executable action for '{item.title}'."
        return observation

    async def _execute_item(
        self,
        item: PlanItem,
        plan: PlanReactPlan,
        scratchpad: List[Dict[str, str]],
        authorized_tools: Dict[str, ToolExecutionContext],
    ) -> str:
        if item.status == StepStatus.READY and item.plugin_name and item.tool_name and self._tool_gateway:
            observation = await self._execute_ready_item(item, authorized_tools)
        elif item.status == StepStatus.MANUAL:
            observation = f"Manual execution required for '{item.title}'."
        elif item.status == StepStatus.BLOCKED:
            observation = f"Capability '{item.capability}' missing; step marked blocked."
        elif item.status == StepStatus.SKIPPED:
            observation = f"Step '{item.title}' skipped based on human instruction."
        elif item.status == StepStatus.NEEDS_DATA:
            observation = await self._handle_runtime_data_request(item)
        else:
            observation = f"No executable action for '{item.title}'."
        return observation

    async def _execute_ready_item(
        self,
        item: PlanItem,
        authorized_tools: Dict[str, ToolExecutionContext],
        action_decision: ActionDecision,
        scratchpad: List[Dict[str, str]],
        plan_context: Dict[str, Any],
    ) -> str:
        key = f"{item.plugin_name}.{item.tool_name}"
        tool_ctx: Optional[ToolExecutionContext] = authorized_tools.get(key)
        if not tool_ctx:
            item.status = StepStatus.BLOCKED
            return f"Tool {key} not authorized; marking step blocked."

        if not self._tool_gateway.ensure_approval("plan-react", tool_ctx):
            item.status = StepStatus.BLOCKED
            return f"Tool {key} was not approved; step halted."

        # Execute tool with parameters
        observation = await self._execute_tool_with_params(
            tool_ctx, action_decision, item, scratchpad, plan_context
        )
        return observation

    async def _handle_runtime_data_request(self, item: PlanItem) -> str:
        if not self._approval_service:
            return f"Data requested for '{item.title}' but approval service unavailable."

        approval_request = ApprovalRequest(
            workflow_id="plan-react",
            plugin_name="RuntimeData",
            tool_name=item.title,
            risk_level=RiskLevel.LOW,
            rationale="Executor requires additional runtime data to proceed",
            approval_type=ApprovalType.RUNTIME_DATA,
            phase="execution",
            planning_context={
                "step_title": item.title,
                "required_fields": list(item.runtime_data_schema.keys()),
            },
        )
        decision = self._approval_service.request_approval(approval_request)

        if decision.approved:
            if self._feedback_store:
                self._feedback_store.record(
                    workflow_id="plan-react",
                    phase="execution",
                    note=f"Runtime data provided for {item.title}",
                    metadata={"reviewer": decision.reviewer},
                )
            return f"Runtime data supplied; step '{item.title}' ready to proceed manually."
        return f"Runtime data request declined for '{item.title}'."

    async def _request_extension(self, plan: PlanReactPlan) -> str:
        if not self._approval_service:
            return "Extension requested but approval service unavailable."

        approval_req = ApprovalRequest(
            workflow_id="plan-react",
            plugin_name="PlanReactCoordinator",
            tool_name="extend_step_budget",
            risk_level=RiskLevel.MEDIUM,
            rationale="Step budget exhausted during reactive execution",
            approval_type=ApprovalType.RUNTIME_DATA,
            phase="execution",
        )
        decision = self._approval_service.request_approval(approval_req)
        return decision.reason or "Extension decision recorded."

    def _synthesise_response(
        self,
        task: str,
        traces: List[ExecutionTrace],
        scratchpad: List[Dict[str, str]],
    ) -> str:
        highlights = ", ".join(entry["observation"] for entry in scratchpad) if scratchpad else "no actions"
        return f"Task '{task}' addressed with reactive execution; observations: {highlights}."

    async def _llm_reason(
        self,
        item: PlanItem,
        scratchpad: List[Dict[str, str]],
        plan_context: Dict[str, Any],
        task: str,
    ) -> str:
        """Use LLM to reason about current state and what to do next."""
        services = self._kernel.get_services_by_type(ChatCompletionClientBase)
        if not services:
            # Fallback to simple reasoning
            if not scratchpad:
                return f"Starting with step {item.step_number}: {item.title}"
            last_obs = scratchpad[-1]["observation"]
            return f"After observing '{last_obs}', evaluate next step {item.step_number}: {item.title}"

        service = services[0]
        settings = service.instantiate_prompt_execution_settings()

        # Build execution history
        history = "\n".join(
            [f"- {entry['title']}: {entry['observation']}" for entry in scratchpad]
        )

        prompt = f"""You are a ReAct agent executing a task step-by-step.

Task: {task}
Overall Goal: {plan_context.get('prompt_context', 'Complete the task successfully')}

Current Step #{item.step_number}:
Title: {item.title}
Success Criteria: {item.success_criteria}
Capability Required: {item.capability or 'general'}

Execution History So Far:
{history if history else '(No prior steps executed)'}

Based on the observations so far, provide your reasoning:
1. What have we learned from previous steps?
2. Is the current step still relevant given what we've observed?
3. What should we focus on for this step?
4. Are there any risks or concerns?

Provide concise reasoning (2-4 sentences):"""

        response = await service.get_chat_message_content([], settings, prompt=prompt)
        if response and response.content:
            return response.content.strip()

        return f"Proceeding with step {item.step_number}: {item.title}"

    async def _llm_decide_action_with_params(
        self,
        thought: str,
        item: PlanItem,
        authorized_tools: Dict[str, ToolExecutionContext],
        scratchpad: List[Dict[str, str]],
        plan_context: Dict[str, Any],
    ) -> ActionDecision:
        """LLM decides action AND parameters in single unified call."""
        services = self._kernel.get_services_by_type(ChatCompletionClientBase)
        if not services:
            # Fallback: default behavior
            if item.status == StepStatus.READY and item.plugin_name and item.tool_name:
                return ActionDecision(
                    action_type=ActionType.EXECUTE_TOOL,
                    tool_name=f"{item.plugin_name}.{item.tool_name}",
                    rationale="Default action for ready step",
                )
            return ActionDecision(
                action_type=ActionType.SKIP_STEP,
                rationale="Step not ready for execution",
            )

        service = services[0]
        settings = service.instantiate_prompt_execution_settings()

        # Build detailed tool catalog with schemas
        tool_catalog = []
        for tool_name, tool_ctx in authorized_tools.items():
            schema = self._build_tool_schema_for_llm(tool_ctx)
            tool_catalog.append(schema)

        # Format execution history
        history_str = self._format_scratchpad(scratchpad)

        prompt = f"""You are a ReAct agent deciding the next action WITH parameters.

Reasoning: {thought}

Current Step #{item.step_number}:
Title: {item.title}
Success Criteria: {item.success_criteria}
Status: {item.status.value}
Mapped Tool: {item.plugin_name}.{item.tool_name if item.plugin_name and item.tool_name else 'None'}

Execution History:
{history_str}

Plan Context:
{json.dumps(plan_context, indent=2) if plan_context else '(No additional context)'}

Available Tools (with schemas):
{json.dumps(tool_catalog, indent=2)}

Decide the next action AND provide parameters. Respond ONLY with valid JSON:
{{
  "action_type": "execute_tool" | "skip_step" | "terminate" | "request_replan",
  "tool_name": "plugin.tool" (only if execute_tool),
  "parameters": {{
    "param1": "value1",
    "param2": "value2"
  }},
  "rationale": "why this action and these parameter values",
  "confidence": 0.0 to 1.0
}}

Guidelines:
- If execute_tool, you MUST provide parameters based on tool schema
- Use context/history to infer appropriate parameter values
- If you cannot determine parameters, set confidence < 0.5 or use skip_step
- For terminate, explain why the task goal is achieved
- For request_replan, explain why the plan is no longer valid

JSON response:"""

        response = await service.get_chat_message_content([], settings, prompt=prompt)
        if response and response.content:
            try:
                # Extract JSON from response
                content = response.content.strip()
                # Handle markdown code blocks
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()

                data = json.loads(content)
                action_decision = ActionDecision(**data)

                # Hybrid fallback: If confident but no params, try separate inference
                if (
                    action_decision.action_type == ActionType.EXECUTE_TOOL
                    and not action_decision.parameters
                    and action_decision.confidence > 0.7
                ):
                    self._logger.info(
                        f"LLM confident about tool choice but no params provided. "
                        f"Falling back to separate parameter inference."
                    )
                    tool_ctx = authorized_tools.get(action_decision.tool_name)
                    if tool_ctx:
                        action_decision.parameters = await self._llm_infer_parameters(
                            tool_ctx, item, scratchpad, plan_context
                        )

                return action_decision
            except (json.JSONDecodeError, ValidationError) as ex:
                self._logger.warning(f"Failed to parse LLM action decision: {ex}")

        # Fallback
        if item.status == StepStatus.READY and item.plugin_name and item.tool_name:
            return ActionDecision(
                action_type=ActionType.EXECUTE_TOOL,
                tool_name=f"{item.plugin_name}.{item.tool_name}",
                rationale="Fallback: executing mapped tool",
            )
        return ActionDecision(
            action_type=ActionType.SKIP_STEP,
            rationale="Fallback: no clear action available",
        )

    async def _llm_infer_parameters(
        self,
        tool_ctx: ToolExecutionContext,
        item: PlanItem,
        scratchpad: List[Dict[str, str]],
        plan_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Use LLM to infer tool parameters from context."""
        services = self._kernel.get_services_by_type(ChatCompletionClientBase)
        if not services:
            # Fallback: return empty parameters
            self._logger.warning(
                f"No LLM service available for parameter inference for {tool_ctx.plugin_name}.{tool_ctx.tool_name}"
            )
            return {}

        service = services[0]
        settings = service.instantiate_prompt_execution_settings()

        # Build execution history
        history = "\n".join(
            [f"- {entry['title']}: {entry['observation']}" for entry in scratchpad]
        )

        # Get tool metadata
        tool_desc = tool_ctx.definition.description
        tool_params = getattr(tool_ctx.definition, "parameters", {})

        prompt = f"""You are inferring parameters for a tool invocation based on execution context.

Tool: {tool_ctx.plugin_name}.{tool_ctx.tool_name}
Description: {tool_desc}
Parameters: {json.dumps(tool_params, indent=2) if tool_params else '(No parameter schema available)'}

Current Step: {item.title}
Success Criteria: {item.success_criteria}

Execution History:
{history if history else '(No prior steps)'}

Plan Context:
{json.dumps(plan_context, indent=2) if plan_context else '(No additional context)'}

Based on the above context, infer the appropriate parameter values for this tool.
Respond ONLY with valid JSON containing parameter name-value pairs:
{{
  "param1": "value1",
  "param2": "value2"
}}

If you cannot infer parameters, return an empty object: {{}}

JSON response:"""

        response = await service.get_chat_message_content([], settings, prompt=prompt)
        if response and response.content:
            try:
                content = response.content.strip()
                # Handle markdown code blocks
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()

                params = json.loads(content)
                self._logger.info(f"Inferred parameters for {tool_ctx.tool_name}: {params}")
                return params
            except (json.JSONDecodeError, ValidationError) as ex:
                self._logger.warning(f"Failed to parse inferred parameters: {ex}")

        return {}

    def _validate_parameters(
        self,
        parameters: Dict[str, Any],
        tool_ctx: ToolExecutionContext,
    ) -> tuple[bool, Optional[str]]:
        """Validate parameters against tool schema.

        Returns:
            (is_valid, error_message) tuple
        """
        function_metadata = tool_ctx.function.metadata

        # Check if we have parameter metadata
        if not hasattr(function_metadata, "parameters") or not function_metadata.parameters:
            # No schema to validate against, allow it
            return True, None

        # Check required parameters
        for param in function_metadata.parameters:
            param_name = param.name
            is_required = param.is_required if hasattr(param, "is_required") else False

            if is_required and param_name not in parameters:
                return False, f"Missing required parameter: {param_name}"

        # Check for unexpected parameters (optional - could be too strict)
        expected_params = {p.name for p in function_metadata.parameters}
        unexpected = set(parameters.keys()) - expected_params
        if unexpected:
            self._logger.warning(
                f"Unexpected parameters for {tool_ctx.tool_name}: {unexpected}"
            )

        return True, None

    async def _request_tool_execution_approval(
        self,
        tool_ctx: ToolExecutionContext,
        parameters: Dict[str, Any],
        action_decision: ActionDecision,
        item: PlanItem,
    ) -> bool:
        """Request HITL approval for tool execution with parameters visible.

        This combines the tool choice and parameter approval into a single checkpoint.
        """
        if not self._approval_service:
            return True  # No approval service, auto-approve

        from src.policies.approval_service import ApprovalRequest
        from src.policies.policy_models import ApprovalType

        # Build approval request
        approval_req = ApprovalRequest(
            workflow_id="plan-react",
            plugin_name=tool_ctx.plugin_name,
            tool_name=tool_ctx.tool_name,
            risk_level=tool_ctx.definition.risk_level,
            rationale=action_decision.rationale,
            approval_type=ApprovalType.OPERATIONAL_DECISION,
            phase="execution",
            planning_context={
                "step_number": item.step_number,
                "step_title": item.title,
                "success_criteria": item.success_criteria,
                "action_confidence": action_decision.confidence,
                "parameters": parameters,  # Show parameters to human!
                "tool_description": tool_ctx.definition.description,
            },
        )

        decision = self._approval_service.request_approval(approval_req)

        # Log feedback if available
        if self._feedback_store and decision.reason:
            self._feedback_store.record(
                workflow_id="plan-react",
                phase="tool-execution-approval",
                note=decision.reason,
                metadata={
                    "tool": f"{tool_ctx.plugin_name}.{tool_ctx.tool_name}",
                    "approved": decision.approved,
                    "parameters": parameters,
                },
            )

        return decision.approved

    async def _execute_tool_with_params(
        self,
        tool_ctx: ToolExecutionContext,
        action_decision: ActionDecision,
        item: PlanItem,
        scratchpad: List[Dict[str, str]],
        plan_context: Dict[str, Any],
    ) -> str:
        """Execute tool with parameters from unified decision.

        Parameters now come from action_decision (populated by _llm_decide_action_with_params).
        """
        # Get parameters from decision (already inferred in unified call)
        parameters = action_decision.parameters

        # If no parameters and confidence is high, try fallback inference
        if not parameters and action_decision.confidence > 0.7:
            self._logger.info(
                f"No parameters in action decision, attempting fallback inference for {tool_ctx.tool_name}"
            )
            parameters = await self._llm_infer_parameters(
                tool_ctx, item, scratchpad, plan_context
            )

        # Validate parameters against schema
        is_valid, error = self._validate_parameters(parameters, tool_ctx)
        if not is_valid:
            error_msg = f"Parameter validation failed for {tool_ctx.tool_name}: {error}"
            self._logger.error(error_msg)
            return error_msg

        # Request HITL approval (shows both tool and parameters)
        if not await self._request_tool_execution_approval(tool_ctx, parameters, action_decision, item):
            return f"Tool execution denied by human: {tool_ctx.plugin_name}.{tool_ctx.tool_name}"

        # Log parameter usage for telemetry
        if self._telemetry:
            self._telemetry.record_agent_execution(
                agent_name="ReactivePlanReactExecutorStep.ToolInvocation",
                duration_seconds=0.0,
                success=True,
                tags={
                    "tool": f"{tool_ctx.plugin_name}.{tool_ctx.tool_name}",
                    "step": str(item.step_number),
                    "has_parameters": str(bool(parameters)).lower(),
                    "parameter_count": str(len(parameters)),
                },
            )

        # Invoke the tool
        try:
            self._logger.info(
                f"Invoking {tool_ctx.plugin_name}.{tool_ctx.tool_name} with params: {parameters}"
            )
            result = await tool_ctx.function.invoke(self._kernel, **parameters)

            # Extract result value
            observation = str(result.value) if result and hasattr(result, "value") else str(result)
            self._logger.info(f"Tool execution result: {observation[:200]}")
            return observation

        except Exception as ex:
            error_msg = f"Tool {tool_ctx.plugin_name}.{tool_ctx.tool_name} failed: {str(ex)}"
            self._logger.error(error_msg)
            return error_msg

    def _detect_divergence(
        self,
        item: PlanItem,
        observation: str,
        action_decision: ActionDecision,
        scratchpad: List[Dict[str, str]],
    ) -> Optional[DivergenceSignal]:
        """Detect if observations contradict plan assumptions."""
        observation_lower = observation.lower()

        # Critical: Tool execution failures
        if any(keyword in observation_lower for keyword in ["failed", "error", "exception", "not found"]):
            return DivergenceSignal(
                severity=DivergenceSeverity.MODERATE,
                step_number=item.step_number,
                reason="Tool execution failed or error detected",
                observed_state=observation[:200],
                expected_state=item.success_criteria,
                recommendation=ActionType.REQUEST_REPLAN,
                context={"action_confidence": action_decision.confidence},
            )

        # Moderate: Action decision suggests replan
        if action_decision.action_type == ActionType.REQUEST_REPLAN:
            return DivergenceSignal(
                severity=DivergenceSeverity.CRITICAL,
                step_number=item.step_number,
                reason=f"LLM recommended re-planning: {action_decision.rationale}",
                observed_state=observation[:200],
                expected_state=item.success_criteria,
                recommendation=ActionType.REQUEST_REPLAN,
                context={"decision_rationale": action_decision.rationale},
            )

        # Minor: Low confidence action
        if action_decision.confidence < 0.5:
            return DivergenceSignal(
                severity=DivergenceSeverity.MINOR,
                step_number=item.step_number,
                reason=f"Low confidence action ({action_decision.confidence:.2f})",
                observed_state=observation[:200],
                expected_state=item.success_criteria,
                recommendation=ActionType.SKIP_STEP,
                context={"confidence": action_decision.confidence},
            )

        return None

    def _should_terminate_early(
        self,
        task: str,
        traces: List[ExecutionTrace],
        scratchpad: List[Dict[str, str]],
    ) -> bool:
        """Check if task goal is already achieved before plan completion."""
        # Heuristic: if last observation suggests completion
        if not scratchpad:
            return False

        last_obs = scratchpad[-1]["observation"].lower()
        completion_keywords = ["complete", "finished", "done", "successful", "resolved"]

        return any(keyword in last_obs for keyword in completion_keywords)

    def _build_tool_schema_for_llm(self, tool_ctx: ToolExecutionContext) -> Dict[str, Any]:
        """Build comprehensive tool schema for LLM decision-making."""
        # Get SK function metadata
        function_metadata = tool_ctx.function.metadata

        # Get our custom metadata
        tool_definition = tool_ctx.definition

        # Build parameter schema from SK metadata
        parameters = {}
        if hasattr(function_metadata, "parameters") and function_metadata.parameters:
            for param in function_metadata.parameters:
                param_info = {
                    "type": str(param.type_) if hasattr(param, "type_") else "string",
                    "description": param.description if hasattr(param, "description") else "",
                    "required": param.is_required if hasattr(param, "is_required") else False,
                }
                if hasattr(param, "default_value") and param.default_value is not None:
                    param_info["default"] = str(param.default_value)

                parameters[param.name] = param_info

        # Enhance with our custom metadata
        if hasattr(tool_definition, "inputs") and tool_definition.inputs:
            for tool_input in tool_definition.inputs:
                if tool_input.name in parameters:
                    # Enhance existing param
                    parameters[tool_input.name]["description"] = tool_input.description
                    parameters[tool_input.name]["required"] = tool_input.required
                else:
                    # Add new param from custom metadata
                    parameters[tool_input.name] = {
                        "type": tool_input.type_hint if hasattr(tool_input, "type_hint") else "string",
                        "description": tool_input.description,
                        "required": tool_input.required,
                    }

        return {
            "tool_name": f"{tool_ctx.plugin_name}.{tool_ctx.tool_name}",
            "description": tool_definition.description,
            "parameters": parameters,
            "sample_output": (
                tool_definition.sample_output
                if hasattr(tool_definition, "sample_output")
                else None
            ),
            "risk_level": tool_ctx.definition.risk_level.value,
        }

    def _format_scratchpad(self, scratchpad: List[Dict[str, str]]) -> str:
        """Format scratchpad for LLM prompt."""
        if not scratchpad:
            return "(No prior steps executed)"

        lines = []
        for entry in scratchpad:
            lines.append(f"- {entry['title']}: {entry['observation'][:150]}")
        return "\n".join(lines)

    def _build_replan_context(
        self,
        plan: PlanReactPlan,
        traces: List[ExecutionTrace],
        scratchpad: List[Dict[str, str]],
        divergence: DivergenceSignal,
        processed: set[int],
        remaining_budget: int,
    ) -> ReplanContext:
        """Build context for coordinator-level re-planning."""
        lessons = []

        # Extract lessons from traces
        for trace in traces:
            if trace.divergence:
                lessons.append(f"Step {trace.sequence} diverged: {trace.divergence.reason}")
            if any(keyword in trace.observation.lower() for keyword in ["error", "failed", "exception"]):
                lessons.append(f"Step {trace.sequence} encountered issue: {trace.observation[:100]}")

        # Add divergence summary
        lessons.append(f"Critical divergence at step {divergence.step_number}: {divergence.reason}")

        return ReplanContext(
            original_plan=plan,
            execution_history=traces,
            scratchpad=scratchpad,
            divergence=divergence,
            completed_steps=list(processed),
            remaining_budget=remaining_budget,
            lessons_learned=lessons,
        )


__all__ = ["ReactivePlanReactExecutorStep"]
