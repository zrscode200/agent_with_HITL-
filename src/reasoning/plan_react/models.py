"""Typed models that support the Plan→ReAct workflow."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, PositiveInt


class PlanReactRequest(BaseModel):
    """User input for the deterministic Plan→ReAct pipeline."""

    task: str = Field(..., description="Primary task or question the agent should solve.")
    step_budget: PositiveInt = Field(..., description="Maximum reasoning steps allowed before escalation.")
    allow_step_extension: bool = Field(
        default=True,
        description="Whether the agent may request additional steps from a human when the budget is exceeded.",
    )
    context: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary context shared with planning stage.")
    hints: List[str] = Field(default_factory=list, description="Optional hints nudging planning/execution.")


class PlanItem(BaseModel):
    """Single entry in the generated plan."""

    step_number: PositiveInt
    title: str
    success_criteria: str = Field(default="", description="What success looks like for this step.")


class PlanReactPlan(BaseModel):
    """Structured plan returned by the planner step."""

    task: str
    rationale: str
    step_budget: PositiveInt
    allow_step_extension: bool
    plan: List[PlanItem] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)


class ExecutionTrace(BaseModel):
    """Trace for a single reasoning-action-observation loop."""

    sequence: PositiveInt
    thought: str
    action: str
    observation: str


class PlanReactResult(BaseModel):
    """Final outcome from executing the plan."""

    task: str
    final_response: str
    steps_executed: int
    plan: PlanReactPlan
    traces: List[ExecutionTrace] = Field(default_factory=list)
    extension_requested: bool = False
    extension_message: Optional[str] = None


class PlanReactPlannerState(BaseModel):
    """State container for the planner step."""

    last_plan: Optional[PlanReactPlan] = None


class PlanReactExecutorState(BaseModel):
    """State container for the executor step."""

    last_result: Optional[PlanReactResult] = None
    remaining_budget: int = 0


class PlanReactConfiguration(BaseModel):
    """Configuration knobs for the coordinator."""

    default_step_budget: PositiveInt = Field(default=6, description="Fallback step limit when request omits it.")
    max_supersteps: PositiveInt = Field(
        default=120, description="Safety limit for the underlying process superstep execution."
    )
