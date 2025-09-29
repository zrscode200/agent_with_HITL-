"""Prompt profile definitions for agent workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(slots=True)
class PromptProfile:
    """Represents a reusable set of prompt guidelines."""

    name: str
    system_prompt: str
    style_guidelines: List[str] = field(default_factory=list)
    safety_notes: List[str] = field(default_factory=list)
    additional_context: Dict[str, str] = field(default_factory=dict)

    def render(self) -> str:
        """Render the profile into a single string block."""
        buffer: List[str] = [self.system_prompt.strip()]

        if self.style_guidelines:
            buffer.append("### Style Guidelines")
            buffer.extend(f"- {item}" for item in self.style_guidelines)

        if self.safety_notes:
            buffer.append("### Safety Notes")
            buffer.extend(f"- {item}" for item in self.safety_notes)

        if self.additional_context:
            buffer.append("### Additional Context")
            for key, value in self.additional_context.items():
                buffer.append(f"- {key}: {value}")

        return "\n".join(buffer)


DEFAULT_PROFILE = PromptProfile(
    name="default",
    system_prompt="You are a helpful AI agent.",
    style_guidelines=[
        "Use concise, step-by-step reasoning.",
        "Cite data sources when possible.",
    ],
    safety_notes=[
        "Escalate when unsure rather than guessing.",
    ],
)


__all__ = ["PromptProfile", "DEFAULT_PROFILE"]
