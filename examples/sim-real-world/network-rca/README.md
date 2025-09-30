# Wi-Fi Root Cause Analysis Demo

This simulated real-world scenario demonstrates how to build a Wi-Fi RCA agent on top of the platform’s Plan→ReAct workflow, governance policies, and HITL approvals.

## Scenario Overview
- **Incident:** Corporate Wi-Fi outage on HQ Floor 3.
- **Data Provided:** Alerts, telemetry metrics, topology, and change log snapshots.
- **Goal:** Use the agent to analyze data, correlate changes, and propose remediation steps while capturing human feedback.

## Quick Start
1. Ensure your `.env` contains an OpenAI key and model (e.g., `OPENAI_MODEL_ID=gpt-4o-mini`).
2. From repo root:
   ```bash
   python examples/sim-real-world/network-rca/demo.py
   ```
3. Optional: use `/note` in interactive mode (or edit `demo.py`) to add engineer insights before execution.

## Files
- `data/alerts.json` – simulated Wi-Fi alerts.
- `data/topology.json` – AP/controller relationships.
- `data/wifi_metrics.json` – performance metrics per AP/SSID.
- `data/change_log.json` – recent configuration changes.
- `runbooks.json` – Wi-Fi RCA playbook sections.
- `examples.json` – few-shot examples for planning prompts.

## Demonstrated Features
- Prompt/context assembling (profiles, runbooks, examples, human notes).
- Tool governance (`WifiDiagnosticsPlugin`).
- HITL approvals and feedback logging (`logs/feedback.jsonl`).
- Telemetry for policy decisions and approvals.
