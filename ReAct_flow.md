
  ┌─────────────────────────────────────────────────────────────────┐
  │ 1. INITIALIZATION (Executor Startup)                            │
  ├─────────────────────────────────────────────────────────────────┤
  │ ReactivePlanReactExecutorStep.execute_plan()                    │
  │   ↓                                                              │
  │ authorized_tools = tool_gateway.list_authorized_tools()         │
  │   ↓                                                              │
  │ Returns: Dict[str, ToolExecutionContext]                        │
  │   - Key: "plugin.tool" (e.g., "NetworkPlugin.ping")            │
  │   - Value: {                                                     │
  │       plugin_name: "NetworkPlugin",                             │
  │       tool_name: "ping",                                        │
  │       definition: ToolDefinition (metadata),                    │
  │       function: KernelFunction (executable),                    │
  │       approval_required: bool,                                  │
  │       approved: bool                                            │
  │     }                                                            │
  └─────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────┐
  │ 2. REACT LOOP (Per Step)                                        │
  ├─────────────────────────────────────────────────────────────────┤
  │ For each item in plan.plan:                                     │
  │                                                                  │
  │   ┌─────────────────────────────────────────┐                  │
  │   │ 2a. THINK: Generate Reasoning            │                  │
  │   └─────────────────────────────────────────┘                  │
  │   thought = await _llm_reason(item, scratchpad, context)       │
  │     ↓                                                            │
  │   LLM Prompt:                                                   │
  │     "You are a ReAct agent executing step-by-step.             │
  │      Current Step: {item.title}                                │
  │      Success Criteria: {item.success_criteria}                 │
  │      Execution History: {scratchpad}                           │
  │      Provide your reasoning..."                                │
  │     ↓                                                            │
  │   Returns: "Based on previous network errors, I need to        │
  │             check connectivity using a diagnostic tool..."     │
  │                                                                  │
  │   ┌─────────────────────────────────────────┐                  │
  │   │ 2b. ACT: Decide Action                  │                  │
  │   └─────────────────────────────────────────┘                  │
  │   action_decision = await _llm_decide_action(                  │
  │       thought, item, authorized_tools, scratchpad              │
  │   )                                                             │
  │     ↓                                                            │
  │   LLM Prompt:                                                   │
  │     "Reasoning: {thought}                                      │
  │      Current Step: {item.title}                                │
  │      Available Tools:                                          │
  │        - NetworkPlugin.ping                                    │
  │        - NetworkPlugin.traceroute                              │
  │        - WifiPlugin.scan_networks                              │
  │      Decide the next action (JSON):                            │
  │      {                                                          │
  │        action_type: 'execute_tool',                            │
  │        tool_name: 'NetworkPlugin.ping',                        │
  │        rationale: 'Need to test connectivity',                 │
  │        confidence: 0.9                                         │
  │      }"                                                         │
  │     ↓                                                            │
  │   Returns: ActionDecision(                                     │
  │       action_type=EXECUTE_TOOL,                                │
  │       tool_name="NetworkPlugin.ping",                          │
  │       parameters={},  # Empty at this point                    │
  │       rationale="...",                                         │
  │       confidence=0.9                                           │
  │   )                                                             │
  └─────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────┐
  │ 3. TOOL EXECUTION                                                │
  ├─────────────────────────────────────────────────────────────────┤
  │   if action_decision.action_type == EXECUTE_TOOL:              │
  │                                                                  │
  │   ┌─────────────────────────────────────────┐                  │
  │   │ 3a. Get Tool Context                     │                  │
  │   └─────────────────────────────────────────┘                  │
  │   key = "NetworkPlugin.ping"                                   │
  │   tool_ctx = authorized_tools[key]                             │
  │     ↓                                                            │
  │   tool_ctx contains:                                           │
  │     - function: The actual KernelFunction                      │
  │     - definition: Tool metadata (params, description)          │
  │     - approval_required: bool                                  │
  │                                                                  │
  │   ┌─────────────────────────────────────────┐                  │
  │   │ 3b. Check Approval (HITL Gate)          │                  │
  │   └─────────────────────────────────────────┘                  │
  │   if tool_ctx.approval_required:                               │
  │       approved = tool_gateway.ensure_approval(workflow, tool)  │
  │       if not approved:                                         │
  │           return "Tool not approved"                           │
  │                                                                  │
  │   ┌─────────────────────────────────────────┐                  │
  │   │ 3c. Infer Parameters                     │                  │
  │   └─────────────────────────────────────────┘                  │
  │   parameters = action_decision.parameters  # Check if provided │
  │   if not parameters:                                           │
  │       parameters = await _llm_infer_parameters(                │
  │           tool_ctx, item, scratchpad, plan_context             │
  │       )                                                         │
  │     ↓                                                            │
  │   LLM Prompt:                                                   │
  │     "Infer parameters for tool invocation                      │
  │      Tool: NetworkPlugin.ping                                  │
  │      Description: Ping a host to check connectivity            │
  │      Parameters:                                               │
  │        {                                                        │
  │          'host': 'string - hostname or IP',                    │
  │          'count': 'int - number of pings (default: 4)'         │
  │        }                                                        │
  │      Current Step: Check network connectivity                  │
  │      Execution History:                                        │
  │        - Step 1: User reported connection issues                │
  │        - Step 2: Need to diagnose network                      │
  │      Infer appropriate parameter values (JSON):                │
  │      { 'host': '8.8.8.8', 'count': 4 }"                       │
  │     ↓                                                            │
  │   Returns: {'host': '8.8.8.8', 'count': 4}                    │
  │                                                                  │
  │   ┌─────────────────────────────────────────┐                  │
  │   │ 3d. INVOKE TOOL (The Key Line!)         │                  │
  │   └─────────────────────────────────────────┘                  │
  │   result = await tool_ctx.function.invoke(                     │
  │       self._kernel,                                            │
  │       **parameters  # {'host': '8.8.8.8', 'count': 4}         │
  │   )                                                             │
  │     ↓                                                            │
  │   This calls the actual plugin function:                       │
  │     @kernel_function                                           │
  │     async def ping(self, host: str, count: int = 4):          │
  │         # Real tool execution happens here                     │
  │         result = subprocess.run(['ping', '-c', str(count),    │
  │                                   host], ...)                  │
  │         return result.stdout                                   │
  │     ↓                                                            │
  │   Returns: FunctionResult(                                     │
  │       value="PING 8.8.8.8: 4 packets transmitted,             │
  │              4 received, 0% packet loss"                       │
  │   )                                                             │
  │                                                                  │
  │   ┌─────────────────────────────────────────┐                  │
  │   │ 3e. Extract Observation                  │                  │
  │   └─────────────────────────────────────────┘                  │
  │   observation = str(result.value)                              │
  │     ↓                                                            │
  │   observation = "PING 8.8.8.8: 4 packets transmitted,         │
  │                  4 received, 0% packet loss"                   │
  └─────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────┐
  │ 4. CREATE TRACE & DETECT DIVERGENCE                             │
  ├─────────────────────────────────────────────────────────────────┤
  │   trace = ExecutionTrace(                                       │
  │       sequence=len(traces) + 1,                                │
  │       thought=thought,  # From step 2a                         │
  │       action="Execute tool: NetworkPlugin.ping",               │
  │       observation=observation,  # From step 3e                 │
  │       action_decision=action_decision  # From step 2b          │
  │   )                                                             │
  │     ↓                                                            │
  │   divergence = _detect_divergence(item, observation, ...)      │
  │     ↓                                                            │
  │   If "failed" or "error" in observation:                       │
  │       return DivergenceSignal(severity=CRITICAL, ...)          │
  │     ↓                                                            │
  │   traces.append(trace)                                         │
  │   scratchpad.append({                                          │
  │       "title": item.title,                                     │
  │       "observation": observation                               │
  │   })                                                            │
  └─────────────────────────────────────────────────────────────────┘
