"""Tests for context assembler and prompt profiles."""

from src.context.context_assembler import ContextAssembler
from src.context.prompt_profile import PromptProfile


def test_context_assembler_builds_prompt():
    profile = PromptProfile(
        name="network_ops",
        system_prompt="You are a network engineer copilot.",
        style_guidelines=["Be concise."],
    )

    assembler = ContextAssembler().with_profile(profile)
    assembler.add_section("Runbook", "Step 1 -> Step 2", priority=10)
    assembler.add_section("Examples", "Input -> Output", priority=5)

    context = assembler.build()
    prompt = context.as_prompt()

    assert "You are a network engineer copilot." in prompt
    assert prompt.index("Runbook") < prompt.index("Examples")
