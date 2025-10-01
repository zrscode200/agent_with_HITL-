# IT Ticket Handling Showcase

This scenario demonstrates the AI Agent Platform on a simulated high-priority VPN ticket. It
highlights runtime composition, context enrichment, deterministic Plan→ReAct reasoning, tool
policy enforcement, scripted human approvals, and telemetry/feedback capture.

## Run the demo

```bash
python examples/sim-real-world/IT-ticket_handling/incident_response_demo.py
```

Requirements:
- `.env` must contain a valid `OPENAI_API_KEY`. The script prints a reminder and continues even if
  Azure OpenAI keys are used instead. To switch providers, set the corresponding `AZURE_OPENAI_*`
  variables and the runtime builder will pick them up automatically.
- The Semantic Kernel dependencies from `requirements.txt` must be installed (run `make setup-dev`).

## What the demo covers
- **Context assembly** – A custom prompt profile, runbook, and few-shot guidance tailored to VPN
  outages are registered with `WorkflowContextManager`.
- **Plan→ReAct pipeline** – A `PlanReactRequest` captures the incident narrative, hints, and
  timeline. The deterministic planner/executor produce a multi-step response while recording
  telemetry.
- **Tool governance** – The demo prints tool policy decisions, swaps in a scripted
  `ConsoleApprovalService`, and walks through approving the high-risk document validation tool.
- **Plugin usage** – The Document Processing plugin analyzes gateway logs and validates an incident
  report draft; the Wi-Fi Diagnostics plugin surfaces correlated metrics.
- **Telemetry & feedback** – The `TelemetryService` is initialized, and pre/post-run human notes are
  logged to `logs/feedback.jsonl` for audit trails.

## Extending the scenario
- Add additional tooling (e.g., a CMDB plugin) and register it via `PluginManager` to expand the
  incident workflow.
- Replace the scripted approval input with real console interaction for live demos.
- Point the HTTP plugin at synthetic status endpoints if you want to incorporate external checks.
