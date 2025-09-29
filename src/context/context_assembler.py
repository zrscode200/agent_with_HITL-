"""Context assembly utilities for workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from src.context.prompt_profile import PromptProfile, DEFAULT_PROFILE
from src.context.runbook_loader import Runbook, RunbookSection
from src.context.example_loader import FewShotExample


@dataclass(slots=True)
class ContextSection:
    """Individual piece of context included in the prompt."""

    title: str
    content: str
    priority: int = 0


@dataclass(slots=True)
class AssembledContext:
    """Final context package provided to planners/executors."""

    profile: PromptProfile
    sections: List[ContextSection]

    def as_prompt(self) -> str:
        """Render the assembled context into a prompt string."""
        parts = [self.profile.render()]
        for section in sorted(self.sections, key=lambda item: item.priority, reverse=True):
            parts.append(f"### {section.title}\n{section.content.strip()}")
        return "\n\n".join(parts)


@dataclass(slots=True)
class ContextAssembler:
    """Collects prompt profile, runbooks, examples, and human notes."""

    profile: PromptProfile = field(default_factory=lambda: DEFAULT_PROFILE)
    _sections: List[ContextSection] = field(default_factory=list)

    def with_profile(self, profile: PromptProfile) -> "ContextAssembler":
        self.profile = profile
        return self

    def add_section(
        self,
        title: str,
        content: str,
        *,
        priority: int = 0,
    ) -> "ContextAssembler":
        self._sections.append(ContextSection(title=title, content=content, priority=priority))
        return self

    def add_runbook(
        self,
        runbook: Runbook,
        *,
        include_sections: Optional[Iterable[str]] = None,
    ) -> "ContextAssembler":
        sections = runbook.get_sections(include_sections)
        for section in sections:
            self.add_section(
                title=f"Runbook: {section.title}",
                content=section.content,
                priority=section.priority,
            )
        return self

    def add_examples(
        self,
        examples: Iterable[FewShotExample],
        *,
        title: str = "Few-Shot Examples",
        priority: int = 0,
    ) -> "ContextAssembler":
        lines: List[str] = []
        for example in examples:
            lines.append(f"### {example.title}")
            lines.append(f"Task: {example.task}")
            if example.reasoning:
                lines.append(f"Reasoning: {example.reasoning}")
            if example.output:
                lines.append(f"Output: {example.output}")
            lines.append("")
        if lines:
            self.add_section(title=title, content="\n".join(lines).strip(), priority=priority)
        return self

    def build(self) -> AssembledContext:
        return AssembledContext(profile=self.profile, sections=list(self._sections))


__all__ = [
    "ContextAssembler",
    "ContextSection",
    "AssembledContext",
]
