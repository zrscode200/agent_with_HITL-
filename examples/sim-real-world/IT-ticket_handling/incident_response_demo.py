"""IT incident response showcase for the AI Agent Platform.

This script demonstrates how the runtime builder, context manager, policy/approval
engine, and Plan→ReAct coordinator work together on a simulated VPN outage.

Usage:
    python examples/sim-real-world/IT-ticket_handling/incident_response_demo.py

Prerequisites:
    - An OpenAI API key set in `.env` as OPENAI_API_KEY (Azure OpenAI supported via env vars)
    - Optional: set AGENT_PLATFORM_ENABLE_HITL=false to skip scripted approval input
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import Settings
from src.context.example_loader import FewShotExample
from src.context.prompt_profile import PromptProfile
from src.context.runbook_loader import Runbook, RunbookSection
from src.observability.telemetry_service import TelemetryService
from src.policies.approval_service import ConsoleApprovalService
from src.reasoning.plan_react.models import PlanReactRequest
from src.reasoning.plan_react.process import PlanReactCoordinator
from src.runtime.runtime_builder import AgentRuntimeBuilder

LOGGER = logging.getLogger("it_incident_demo")
BASE_DIR = Path(__file__).resolve().parent
PAYLOAD_PATH = BASE_DIR / "incident_payload.json"


@dataclass
class ScriptedInput:
    """Deterministic console input provider for ConsoleApprovalService."""

    responses: Iterable[str]

    def __post_init__(self) -> None:
        self._buffer: List[str] = list(self.responses)

    def __call__(self, prompt: str) -> str:
        print(prompt, end="")
        if not self._buffer:
            return ""
        return self._buffer.pop(0)


def load_payload() -> dict:
    data = json.loads(PAYLOAD_PATH.read_text())
    required_keys = {
        "incident",
        "timeline",
        "log_excerpt",
        "validation_rules",
        "policy_playbook",
        "human_hints",
        "post_run_note",
        "incident_report_draft",
    }
    missing = required_keys.difference(data)
    if missing:
        raise ValueError(f"Payload missing keys: {', '.join(sorted(missing))}")
    return data


def configure_context(runtime, payload: dict) -> None:
    """Customize prompt profile, runbook, and examples for the incident."""
    profile = PromptProfile(
        name="it-incident-response",
        system_prompt=(
            "You are the incident commander for enterprise IT outages. "
            "Deliver decisive, auditable actions with clear next steps."
        ),
        style_guidelines=[
            "Summaries should list impact, hypothesis, next action.",
            "Surface open questions that need escalation.",
            "Call out where human approval was needed.",
        ],
        safety_notes=[
            "Never modify production systems without change control.",
            "Escalate immediately if customer data loss is suspected.",
        ],
        additional_context={
            "service": payload["incident"]["service"],
            "priority": payload["incident"]["priority"],
        },
    )

    runbook = Runbook(
        runbook_id="it-incident-ticket",
        description="Standard operating procedure for high-priority remote access outages.",
        sections=[
            RunbookSection(
                title="Stabilize",
                content=(
                    "1. Confirm scope with service desk." \
                    "\n2. Review recent change tickets." \
                    "\n3. Check authentication provider health."
                ),
                priority=25,
            ),
            RunbookSection(
                title="Communicate",
                content=(
                    "1. Declare incident bridge if impact > 20% remote staff." \
                    "\n2. Notify leadership and customer success." \
                    "\n3. Publish updates every 15 minutes."
                ),
                priority=20,
            ),
            RunbookSection(
                title="Recover",
                content=(
                    "1. Validate firewall policy state." \
                    "\n2. Roll back suspect changes if mitigation safe." \
                    "\n3. Capture evidence for post-incident review."
                ),
                priority=15,
            ),
        ],
    )

    example = FewShotExample(
        title="VPN outage triage",
        task="Remote staff report authentication failures across regions.",
        reasoning="Inspect gateway logs, correlate with firewall change, validate mitigation plan.",
        output="Rollback change CHG-4420, confirm radius service stable, keep bridge active until error rate <1%.",
    )

    manager = runtime.context_manager
    manager.set_profile(PlanReactCoordinator.WORKFLOW_ID, profile)
    manager.register_runbook(PlanReactCoordinator.WORKFLOW_ID, runbook)
    manager.register_examples(PlanReactCoordinator.WORKFLOW_ID, [example])


async def showcase_features(runtime, payload: dict) -> None:
    """Run the incident scenario highlighting reasoning and tool governance."""
    incident = payload["incident"]

    runtime.plan_react.register_pre_run_note(
        f"Bridge declared for {incident['service']} outage; gather approvals quickly."
    )

    request = PlanReactRequest(
        task=(
            "Assess incident {id}: {summary} Provide immediate stabilization steps, "
            "highlight policy checks, and confirm if firewall change CHG-5571 should roll back.".format(
                id=incident["id"],
                summary=incident["summary"],
            )
        ),
        step_budget=6,
        hints=payload["human_hints"],
        context={
            "incident": incident,
            "timeline": payload["timeline"],
            "runbook_id": "it-incident-ticket",
        },
    )

    result = await runtime.plan_react.run(request)

    print("\n=== Plan→ReAct Result ===")
    print("Final response:\n", result.final_response)
    print("Steps executed:", result.steps_executed)
    print("Plan rationale:", result.plan.rationale)
    for trace in result.traces:
        print(f"  • [{trace.sequence}] {trace.thought} -> {trace.action} | {trace.observation}")

    if result.extension_requested:
        print("Extension requested:", result.extension_message)

    print("\n=== Tool Authorization Snapshot ===")
    authorized = runtime.tool_gateway.list_authorized_tools(PlanReactCoordinator.WORKFLOW_ID)
    for qualified, ctx in authorized.items():
        status = "approval required" if ctx.approval_required else "auto-approved"
        print(f"  - {qualified} ({ctx.definition.risk_level.value} risk): {status}")

    # Replace the approval service with a scripted responder so the demo can run unattended.
    scripted_service = ConsoleApprovalService(
        input_fn=ScriptedInput(["y", "Reviewed runbook before validation."]),
        auto_approve=False,
        telemetry=runtime.telemetry_service,
        logger=LOGGER.getChild("Approval"),
    )
    runtime.approval_service = scripted_service
    runtime.tool_gateway._approval_service = scripted_service  # noqa: SLF001 – controlled demo swap

    validation_ctx = authorized.get("DocumentProcessing.validate_document")
    if validation_ctx:
        approved = runtime.tool_gateway.ensure_approval(
            PlanReactCoordinator.WORKFLOW_ID,
            validation_ctx,
        )
        print("\nApproval granted:", approved)
    else:
        print("\nValidation tool not available; skipping approval demo.")

    doc_plugin = runtime.plugin_manager.get_plugin("DocumentProcessing")
    if doc_plugin:
        analysis_raw = await doc_plugin.analyze_document_async(
            document_content=payload["log_excerpt"],
            document_type="vpn-gateway"
        )
        validation_raw = await doc_plugin.validate_document_async(
            document_content=payload["incident_report_draft"],
            validation_rules=payload["validation_rules"],
            validation_level="strict",
        )
        print("\nDocument analysis summary:")
        print(json.dumps(json.loads(analysis_raw), indent=2))
        print("\nValidation outcome:")
        print(json.dumps(json.loads(validation_raw), indent=2))

    wifi_plugin = runtime.plugin_manager.get_plugin("WifiDiagnostics")
    if wifi_plugin:
        wifi_raw = await wifi_plugin.fetch_metrics_async(entity="SSID-CorpWiFi")
        print("\nWi-Fi metrics snapshot:")
        print(json.dumps(json.loads(wifi_raw), indent=2))

    runtime.plan_react.register_post_run_feedback(payload["post_run_note"])
    print("\nFeedback log written to:", runtime.feedback_store.path)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    payload = load_payload()

    settings = Settings()
    if settings.observability.console_exporter_enabled:
        settings.observability.console_exporter_enabled = False
    LOGGER.info("OpenAI configured: %s", bool(settings.openai))
    LOGGER.info("Azure OpenAI configured: %s", bool(settings.azure_openai))

    telemetry = TelemetryService(settings)
    telemetry.initialize()

    try:
        async with AgentRuntimeBuilder(settings=settings, telemetry_service=telemetry) as runtime:
            configure_context(runtime, payload)
            await showcase_features(runtime, payload)
    finally:
        telemetry.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
