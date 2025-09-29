"""Tests for runbook and example libraries and workflow context manager."""

from pathlib import Path

from src.context.runbook_loader import RunbookLibrary
from src.context.example_loader import FewShotLibrary
from src.context.workflow_context import WorkflowContextManager
from src.reasoning.plan_react.process import PlanReactCoordinator


def test_runbook_library_loads(tmp_path: Path):
    content = {
        "runbooks": [
            {
                "id": "test",
                "description": "Test runbook",
                "sections": [
                    {"title": "Step", "content": "Do something", "priority": 5}
                ],
            }
        ]
    }
    path = tmp_path / "runbooks.json"
    path.write_text(__import__("json").dumps(content))

    library = RunbookLibrary.from_json(path)
    runbook = library.get("test")
    assert runbook.description == "Test runbook"
    assert runbook.get_sections()[0].title == "Step"


def test_workflow_context_manager(tmp_path: Path):
    runbook_content = {
        "runbooks": [
            {
                "id": "plan-react-default",
                "description": "Runbook",
                "sections": [
                    {"title": "Intro", "content": "Intro text", "priority": 1}
                ],
            }
        ]
    }
    runbook_path = tmp_path / "runbooks.json"
    runbook_path.write_text(__import__("json").dumps(runbook_content))

    examples_path = tmp_path / "examples.json"
    examples_path.write_text(
        __import__("json").dumps(
            {
                "examples": {
                    "plan-react": [
                        {
                            "title": "Example",
                            "task": "Diagnose issue",
                            "reasoning": "Check logs",
                            "output": "Plan",
                        }
                    ]
                }
            }
        )
    )

    runbooks = RunbookLibrary.from_json(runbook_path)
    examples = FewShotLibrary.from_json(examples_path)

    manager = WorkflowContextManager()
    manager.register_runbook(PlanReactCoordinator.WORKFLOW_ID, runbooks.get("plan-react-default"))
    manager.register_examples(PlanReactCoordinator.WORKFLOW_ID, examples.get("plan-react"))

    context = manager.assemble(PlanReactCoordinator.WORKFLOW_ID)
    prompt = context.as_prompt()
    assert "Intro text" in prompt
    assert "Example" in prompt
