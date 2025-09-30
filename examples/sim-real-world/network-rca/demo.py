"""Wi-Fi RCA demo leveraging Plan→ReAct and HITL features."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "src"))

from config import Settings
from src.runtime.runtime_builder import AgentRuntimeBuilder
from src.reasoning.plan_react.process import PlanReactCoordinator
from src.plugins.wifi_diagnostics_plugin import WifiDiagnosticsPlugin
from src.context.runbook_loader import RunbookLibrary
from src.context.example_loader import FewShotLibrary

DEMO_DATA_DIR = Path(__file__).parent / "data"
RUNBOOK_PATH = Path(__file__).parent / "runbooks.json"
EXAMPLES_PATH = Path(__file__).parent / "examples.json"


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    settings = Settings()
    async with AgentRuntimeBuilder(settings=settings, logger=logging.getLogger("runtime")) as runtime:
        # Ensure Wi-Fi plugin is registered
        runtime.plugin_manager.register_plugin(WifiDiagnosticsPlugin(logging.getLogger("WiFi")))

        # Load demo runbook and examples into context manager
        runbook_library = RunbookLibrary.from_json(RUNBOOK_PATH)
        runtime.context_manager.register_runbook(
            PlanReactCoordinator.WORKFLOW_ID,
            runbook_library.get("wifi-rca"),
        )
        example_library = FewShotLibrary.from_json(EXAMPLES_PATH)
        runtime.context_manager.register_examples(
            PlanReactCoordinator.WORKFLOW_ID,
            example_library.get("plan-react"),
        )

        # Preview policy decisions
        policy_results = runtime.plugin_manager.get_tools_for_workflow(
            workflow_id=PlanReactCoordinator.WORKFLOW_ID,
            policy_engine=runtime.policy_engine,
        )
        print("Policy decisions for Plan→ReAct (Wi-Fi RCA):")
        for plugin_name, tools in policy_results.items():
            for tool_name, evaluation in tools.items():
                print(
                    f"  - {plugin_name}.{tool_name}: {evaluation.decision.value} "
                    f"({evaluation.rationale})"
                )
        print()

        # Show assembled context preview
        context_preview = runtime.context_manager.assemble(
            PlanReactCoordinator.WORKFLOW_ID,
            clear_notes=False,
        ).as_prompt()
        print("Context preview (truncated):")
        print(context_preview[:400] + ("..." if len(context_preview) > 400 else ""))
        print()

        # Optionally capture a pre-run note
        note = input("Enter pre-run note (press Enter to skip): ")
        if note.strip():
            runtime.plan_react.register_pre_run_note(note)

        # Assemble context and execute Plan→ReAct
        context = runtime.context_manager.assemble(PlanReactCoordinator.WORKFLOW_ID)
        result = await runtime.plan_react.run(
            "Investigate Wi-Fi outage on Floor 3",
            step_budget=4,
            context=context,
        )

        print("\n=== Generated Plan ===")
        for step in result.plan.plan:
            print(f"Step {step.step_number}: {step.title} -> {step.success_criteria}")

        print("\nFinal response:")
        print(result.final_response)

        if result.extension_requested:
            print("Extension requested:", result.extension_message)

        feedback = input("Enter post-run feedback (press Enter to skip): ")
        if feedback.strip():
            runtime.plan_react.register_post_run_feedback(feedback)
            print("Recorded feedback.")

        print("Feedback log stored at:", runtime.feedback_store.path)


if __name__ == "__main__":
    asyncio.run(main())
