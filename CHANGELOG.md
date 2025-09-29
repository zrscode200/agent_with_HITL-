# Changelog

## Unreleased
- Added tool scaffolding script (`scripts/create_plugin.py`) and governance docs.
- Enhanced telemetry to capture policy decisions and approval outcomes.
- Integrated approval service and tool gateway telemetry with runtime builder.
- Added unit tests for telemetry helpers, plugin scaffolding, policy engine, and tool gateway.

## Phase 3 (Sept 2025)
- Human-in-the-loop approval flow with console prompts and auto-approve option.
- Tool gateway now enforces policy decisions and requests approvals before tool execution.

## Phase 2 (Sept 2025)
- Governance metadata via `@tool_spec` and plugin manifests.
- Policy engine with workflow-scoped decisions plus tool gateway integration.

## Phase 1 (Sept 2025)
- Runtime rebuild (`AgentRuntimeBuilder`, `AgentRuntime`) and Plan→ReAct pipeline using SK Processes.
- Updated demos, documentation, and tests to align with the new architecture.
