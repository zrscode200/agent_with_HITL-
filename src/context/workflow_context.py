"""Workflow context manager for assembling prompts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from src.context.context_assembler import ContextAssembler, AssembledContext
from src.context.prompt_profile import PromptProfile, DEFAULT_PROFILE
from src.context.runbook_loader import Runbook
from src.context.example_loader import FewShotExample


@dataclass(slots=True)
class WorkflowContextBinding:
    profile: PromptProfile = field(default_factory=lambda: DEFAULT_PROFILE)
    runbooks: List[tuple[Runbook, Optional[Iterable[str]]]] = field(default_factory=list)
    examples: List[FewShotExample] = field(default_factory=list)
    human_notes: List[tuple[str, str]] = field(default_factory=list)


class WorkflowContextManager:
    """Registers runbooks, examples, and profiles per workflow."""

    def __init__(self) -> None:
        self._bindings: Dict[str, WorkflowContextBinding] = {}

    def set_profile(self, workflow_id: str, profile: PromptProfile) -> None:
        binding = self._bindings.setdefault(workflow_id.lower(), WorkflowContextBinding())
        binding.profile = profile

    def register_runbook(
        self,
        workflow_id: str,
        runbook: Runbook,
        include_sections: Optional[Iterable[str]] = None,
    ) -> None:
        binding = self._bindings.setdefault(workflow_id.lower(), WorkflowContextBinding())
        binding.runbooks.append((runbook, include_sections))

    def register_examples(self, workflow_id: str, examples: Iterable[FewShotExample]) -> None:
        binding = self._bindings.setdefault(workflow_id.lower(), WorkflowContextBinding())
        binding.examples.extend(examples)

    def register_human_note(self, workflow_id: str, phase: str, note: str) -> None:
        binding = self._bindings.setdefault(workflow_id.lower(), WorkflowContextBinding())
        binding.human_notes.append((phase, note))

    def assemble(self, workflow_id: str, *, clear_notes: bool = True) -> AssembledContext:
        binding = self._bindings.get(workflow_id.lower())
        assembler = ContextAssembler()
        if binding:
            assembler.with_profile(binding.profile)
            for runbook, sections in binding.runbooks:
                assembler.add_runbook(runbook, include_sections=sections)
            if binding.examples:
                assembler.add_examples(binding.examples, priority=5)
            if binding.human_notes:
                phase_map: Dict[str, List[str]] = {}
                for phase, note in binding.human_notes:
                    phase_map.setdefault(phase.lower(), []).append(note)
                for phase, notes in phase_map.items():
                    title = f"Human Notes ({phase})"
                    content = "\n".join(f"- {line}" for line in notes)
                    priority = 40 if phase == "pre" else (30 if phase == "mid" else 10)
                    assembler.add_section(title, content, priority=priority)
                if clear_notes:
                    binding.human_notes.clear()
        return assembler.build()


__all__ = ["WorkflowContextManager"]
