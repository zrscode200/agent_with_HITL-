# Two-Phase Planning Implementation Summary

## Overview

Successfully implemented **Hybrid Tool-Informed Planning + Two-Phase Planning** with strategic HITL integration as discussed.

## ✅ Completed Components

### 1. Enhanced Policy & Approval System

**Files Modified:**
- `src/policies/policy_models.py`
- `src/policies/approval_service.py`
- `src/observability/telemetry_service.py`

**Changes:**
- Added `ApprovalType` enum with 5 types:
  - `TOOL_EXECUTION` - Runtime tool approval (existing)
  - `STRATEGIC_REVIEW` - High-level plan review
  - `TACTICAL_FEASIBILITY` - Tool mapping gaps
  - `PLUGIN_INSTALLATION` - Plugin suggestions
  - `RUNTIME_DATA` - Data requests during execution

- Enhanced `ApprovalRequest` with:
  - `approval_type: ApprovalType`
  - `phase: str` (strategic/tactical/execution)
  - `planning_context: Optional[Dict[str, Any]]`

- Enhanced `ConsoleApprovalService` with specialized handlers:
  - `_handle_tool_execution_approval()` - Existing behavior
  - `_handle_feasibility_approval()` - Gap resolution with [skip/manual/alternate/plugin] options
  - `_handle_strategic_review()` - Strategic plan approval
  - `_handle_plugin_approval()` - Plugin queue approval
  - `_handle_runtime_data_request()` - Data collection

- Added `TelemetryService.record_planning_approval()` with separate `PlanningReview.*` namespace

### 2. Plugin Infrastructure

**Files Created:**
- `src/plugins/plugin_suggestions.py`

**Files Modified:**
- `src/plugins/tooling_metadata.py`

**Changes:**
- Created `PluginSuggestionQueue` class:
  - Queues plugin suggestions to `logs/plugin_suggestions.jsonl`
  - No mid-run installations (ops review required)
  - Methods: `suggest_plugin()`, `get_pending_suggestions()`, `get_all_suggestions()`

- Added `ToolCapability` enum:
  - `DOCUMENT_PROCESSING`, `WEB_ACCESS`, `DIAGNOSTICS`
  - `DATA_ANALYSIS`, `COMMUNICATION`, `FILE_OPERATIONS`, `SYSTEM_OPERATIONS`

- Enhanced `ToolDefinition` with:
  - `capabilities: List[ToolCapability]` field
  - Plugins declare their capabilities via `@tool_spec(capabilities=[...])`

### 3. Tool Mapping System

**Files Created:**
- `src/reasoning/plan_react/tool_mapper.py`

**Changes:**
- Created `ToolMapper` class:
  - Builds capability registry from plugin metadata (not hardcoded)
  - `map_step_to_tools()` - Direct capability match or fuzzy fallback
  - Fuzzy matching with confidence scores (logged for compliance)
  - `_suggest_plugin_for_capability()` - Plugin recommendations

- Created supporting models:
  - `StrategicStep` - High-level step representation
  - `ToolMapping` - Mapping result with feasibility, confidence, method

### 4. Enhanced Plan Models

**Files Modified:**
- `src/reasoning/plan_react/models.py`

**Changes:**
- Added `StepStatus` enum:
  - `READY`, `MANUAL`, `BLOCKED`, `NEEDS_DATA`, `SKIPPED`

- Enhanced `PlanReactRequest` with HITL flags:
  - `enable_strategic_hitl: bool` - Optional strategic plan review
  - `enable_feasibility_hitl: bool` - Ask human for tool gaps
  - `auto_install_plugins: bool` - Queue plugin suggestions

- Enhanced `PlanItem` with execution context:
  - `status: StepStatus`
  - `plugin_name`, `tool_name`, `capability`
  - `requires_runtime_data`, `runtime_data_schema`
  - `mapping_confidence`, `mapping_method`, `human_override`

- Created strategic planning models:
  - `StrategicPlanItem` - Tool-agnostic step
  - `StrategicPlan` - High-level plan with `to_prompt()` method
  - `PlanReactPlan.strategic_plan` - Reference to original strategic plan

### 5. Two-Phase Planner

**Files Created:**
- `src/reasoning/plan_react/steps_enhanced.py`

**Files Modified:**
- `src/reasoning/plan_react/steps.py`
- `src/reasoning/plan_react/__init__.py`

**Changes:**
- Created `EnhancedPlanReactPlannerStep`:
  - **Phase 1: Strategic Planning** (`_create_strategic_plan()`)
    - Tool-agnostic, high-level plan
    - LLM-powered or heuristic fallback
    - Optional HITL review (`_review_strategic_plan_with_human()`)

  - **Phase 2: Tactical Planning** (`_create_tactical_plan()`)
    - Maps strategic steps → available tools via `ToolMapper`
    - Handles gaps with `_handle_missing_capability()`:
      - Requests human decision (skip/manual/alternate/plugin)
      - Logs to feedback store and telemetry
      - Queues plugin suggestions (no auto-install)
    - Creates `PlanItem` with proper status and metadata

- Enhanced `PlanReactExecutorStep`:
  - Checks `item.status` before execution
  - Handles `MANUAL`, `BLOCKED`, `SKIPPED`, `NEEDS_DATA` statuses
  - Creates appropriate traces for each status
  - Includes tool info in observations

### 6. Coordinator & Runtime Integration

**Files Modified:**
- `src/reasoning/plan_react/process.py`
- `src/runtime/runtime_builder.py`

**Changes:**
- Enhanced `PlanReactCoordinator.__init__()` with:
  - `approval_service: Optional[ApprovalService]`
  - `plugin_suggestions: Optional[PluginSuggestionQueue]`
  - `tool_manifest: Optional[Dict[str, Dict[str, ToolDefinition]]]`
  - `use_enhanced_planner: bool` - Toggle for two-phase planning

- Updated `_compose_process()`:
  - Selects `EnhancedPlanReactPlannerStep` or `PlanReactPlannerStep` based on flag
  - Injects all dependencies into enhanced planner

- Updated `AgentRuntimeBuilder.build()`:
  - Creates `PluginSuggestionQueue` instance
  - Gets `tool_manifest` from `PluginManager`
  - Reads `enable_two_phase_planning` from settings
  - Wires everything into `PlanReactCoordinator`

## 🎯 HITL Decision Points

The implementation provides **5 strategic HITL triggers**:

```
Strategic Planning
    ├─ enable_strategic_hitl=True
    │   └─► "Does this high-level plan make sense?" [YES/NO/REVISE]
    │
Tactical Planning
    ├─ Missing Tool Detected
    │   ├─ enable_feasibility_hitl=True
    │   │   └─► "Tool X needed. [Skip/Manual/Install/Alternative?]"
    │   └─ enable_feasibility_hitl=False
    │       └─► Automatic fallback (mark as BLOCKED)
    │
    ├─ Ambiguous Tool Match (confidence < 0.8)
    │   └─► Logged with confidence for review
    │
Execution (Existing)
    ├─ Tool Risk > Threshold
    │   └─► Existing approval flow
    │
    ├─ Runtime Data Needed
    │   └─► "Please provide: [field1, field2, ...]"
```

## 📊 Telemetry & Audit Trail

**Separate Namespaces:**
- `PlanningReview.strategic` - Strategic plan approvals
- `PlanningReview.tactical` - Tactical gap decisions
- `ApprovalService` - Tool execution approvals (unchanged)
- `ToolMapper.FuzzyMatch` - Fuzzy matching events with confidence

**Feedback Logging:**
- Phase tags: `strategic-planning`, `tactical-planning`, `execution`
- All decisions logged to `logs/feedback.jsonl`
- Plugin suggestions logged to `logs/plugin_suggestions.jsonl`

## 🔧 Configuration

To enable two-phase planning, add to your settings:

```python
# config.py or .env
class AgentPlatformSettings(BaseSettings):
    enable_human_in_the_loop: bool = True
    enable_two_phase_planning: bool = True  # NEW
```

## 🚀 Usage Example

```python
from src.runtime.runtime_builder import AgentRuntimeBuilder
from src.reasoning.plan_react.models import PlanReactRequest

# Build runtime with two-phase planning enabled
async with AgentRuntimeBuilder(settings=settings) as runtime:

    # Create request with HITL controls
    request = PlanReactRequest(
        task="Analyze this document and extract key insights",
        step_budget=5,
        enable_strategic_hitl=False,  # Skip strategic review
        enable_feasibility_hitl=True,  # Ask for tool gaps
        auto_install_plugins=False,   # Queue plugins, don't auto-install
    )

    # Run two-phase planning
    result = await runtime.plan_react.run(request)

    # Check results
    for trace in result.traces:
        print(f"{trace.action}: {trace.observation}")
```

## 📝 Next Steps

### Immediate:
1. **Add capability declarations to existing plugins**:
   ```python
   @tool_spec(
       capabilities=[ToolCapability.DOCUMENT_PROCESSING],
       risk_level=RiskLevel.HIGH,
   )
   ```

2. **Test two-phase planning**:
   - Run with `enable_two_phase_planning=True`
   - Verify HITL prompts appear correctly
   - Check telemetry namespaces

3. **Update documentation**:
   - Add examples of plugin capability declarations
   - Document HITL decision options

### Optional Enhancements:
- Implement `NEEDS_DATA` runtime data collection
- Add embeddings-based fuzzy matching
- Create dashboard for plugin suggestions review
- Add plan revision/replanning after rejection

## 🎉 Summary

Successfully implemented the full design with your suggestions:
✅ Two-phase planning (strategic → tactical)
✅ Tool-aware tactical planning with capability mapping
✅ HITL at strategic, tactical, and execution phases
✅ Plugin suggestion queue (no mid-run installs)
✅ Separate telemetry namespaces for compliance
✅ Enhanced PlanItem with status and audit fields
✅ Backward compatible (toggle via config)

The implementation follows all your guidance:
- Nested approvals properly separated
- Plugin suggestions queued for ops review
- Reuses existing approval/feedback infrastructure
- Proper phase tagging for filtering
- Tool mapping from metadata (not hardcoded)
- Confidence logging for fuzzy matches
- Clear status tracking for executor

Ready for testing! 🚀
