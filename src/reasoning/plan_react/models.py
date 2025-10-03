"""Typed models that support the Plan→ReAct workflow."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, PositiveInt


class StepStatus(str, Enum):
    """Execution status for plan items."""

    READY = "ready"  # Mapped to tool, ready to execute
    MANUAL = "manual"  # Human will execute manually
    BLOCKED = "blocked"  # Missing capability, cannot proceed
    NEEDS_DATA = "needs_data"  # Requires runtime data input
    SKIPPED = "skipped"  # Human chose to skip


class ActionType(str, Enum):
    """Types of actions the ReAct executor can take."""

    EXECUTE_TOOL = "execute_tool"  # Invoke a tool
    SKIP_STEP = "skip_step"  # Skip current step
    TERMINATE = "terminate"  # Task complete, stop execution
    REQUEST_REPLAN = "request_replan"  # Observations diverge, need new plan


class DivergenceSeverity(str, Enum):
    """Severity levels for plan divergence."""

    MINOR = "minor"  # Small deviation, can continue
    MODERATE = "moderate"  # Significant issue, may need adjustment
    CRITICAL = "critical"  # Plan invalid, re-planning required


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

    # HITL controls for two-phase planning
    enable_strategic_hitl: bool = Field(
        default=False,
        description="Ask human to review strategic plan before tactical planning",
    )
    enable_feasibility_hitl: bool = Field(
        default=True,
        description="Ask human when tools are missing or ambiguous",
    )
    auto_install_plugins: bool = Field(
        default=False,
        description="Automatically suggest plugin installation when gaps detected",
    )


class PlanItem(BaseModel):
    """Single entry in the generated plan."""

    step_number: PositiveInt
    title: str
    success_criteria: str = Field(default="", description="What success looks like for this step.")

    # Execution context (populated by tactical planner)
    status: StepStatus = StepStatus.READY
    plugin_name: Optional[str] = None
    tool_name: Optional[str] = None
    capability: Optional[str] = None
    requires_runtime_data: bool = False
    runtime_data_schema: Dict[str, str] = Field(
        default_factory=dict, description="Field name to description mapping"
    )

    # Mapping metadata for audit trail
    mapping_confidence: float = 1.0
    mapping_method: Optional[str] = None  # "direct" | "fuzzy" | "manual"
    human_override: Optional[str] = None  # If human changed the mapping


class StrategicPlanItem(BaseModel):
    """High-level step from strategic planning (tool-agnostic)."""

    step_number: PositiveInt
    title: str
    required_capability: str
    success_criteria: str
    description: Optional[str] = None


class StrategicPlan(BaseModel):
    """High-level strategic plan (tool-agnostic)."""

    task: str
    goal: str
    rationale: str
    steps: List[StrategicPlanItem] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)

    def to_prompt(self) -> str:
        """Render strategic plan as prompt text."""
        lines = [f"Goal: {self.goal}", f"Rationale: {self.rationale}", "", "Steps:"]
        for step in self.steps:
            lines.append(f"{step.step_number}. {step.title}")
            lines.append(f"   Capability: {step.required_capability}")
            lines.append(f"   Success: {step.success_criteria}")
            if step.description:
                lines.append(f"   Details: {step.description}")
        return "\n".join(lines)


class PlanReactPlan(BaseModel):
    """Structured plan returned by the planner step (tactical, executable)."""

    task: str
    rationale: str
    step_budget: PositiveInt
    allow_step_extension: bool
    plan: List[PlanItem] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    strategic_plan: Optional[StrategicPlan] = None  # Reference to original strategic plan


class ActionDecision(BaseModel):
    """Decision made by LLM about next action to take."""

    action_type: ActionType
    tool_name: Optional[str] = None  # For EXECUTE_TOOL: "plugin.tool"
    parameters: Dict[str, Any] = Field(default_factory=dict)  # Tool parameters
    rationale: str = Field(default="", description="Why this action was chosen")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class DivergenceSignal(BaseModel):
    """Signal indicating execution has diverged from plan expectations."""

    severity: DivergenceSeverity
    step_number: int
    reason: str
    observed_state: str
    expected_state: str
    recommendation: ActionType  # What to do about it
    context: Dict[str, Any] = Field(default_factory=dict)


class ExecutionTrace(BaseModel):
    """Trace for a single reasoning-action-observation loop."""

    sequence: PositiveInt
    thought: str
    action: str
    observation: str
    action_decision: Optional[ActionDecision] = None  # LLM's decision for this step
    divergence: Optional[DivergenceSignal] = None  # Detected divergence if any


class ReplanContext(BaseModel):
    """Context for re-planning after divergence detected."""

    original_plan: PlanReactPlan
    execution_history: List[ExecutionTrace]
    scratchpad: List[Dict[str, Any]]
    divergence: DivergenceSignal
    completed_steps: List[int]
    remaining_budget: int
    lessons_learned: List[str] = Field(default_factory=list)


class PlanReactResult(BaseModel):
    """Final outcome from executing the plan."""

    task: str
    final_response: str
    steps_executed: int
    plan: PlanReactPlan
    traces: List[ExecutionTrace] = Field(default_factory=list)
    extension_requested: bool = False
    extension_message: Optional[str] = None
    replan_requested: bool = False
    replan_context: Optional[ReplanContext] = None


class PlanReactPlannerState(BaseModel):
    """State container for the planner step."""

    last_plan: Optional[PlanReactPlan] = None


class PlanReactExecutorState(BaseModel):
    """State container for the executor step."""

    last_result: Optional[PlanReactResult] = None
    remaining_budget: int = 0
    scratchpad: List[Dict[str, Any]] = Field(default_factory=list)


class PlanReactConfiguration(BaseModel):
    """Configuration knobs for the coordinator."""

    default_step_budget: PositiveInt = Field(default=6, description="Fallback step limit when request omits it.")
    max_supersteps: PositiveInt = Field(
        default=120, description="Safety limit for the underlying process superstep execution."
    )
    max_replans: PositiveInt = Field(default=2, description="Maximum number of re-planning attempts.")
    enable_auto_replan: bool = Field(
        default=True, description="Automatically trigger re-planning on critical divergence."
    )
