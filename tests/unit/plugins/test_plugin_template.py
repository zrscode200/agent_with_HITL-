"""Tests for plugin scaffolding script."""

from pathlib import Path

import pytest

from scripts.create_plugin import generate_plugin_file


def test_generate_plugin_file(tmp_path: Path):
    path = generate_plugin_file(
        class_name="SamplePlugin",
        description="Sample generated plugin",
        risk_level="LOW",
        approval_requirement="NONE",
        output_dir=str(tmp_path),
    )

    assert path.exists()
    content = path.read_text()
    assert "class SamplePlugin" in content
    assert "tool_spec" in content

    with pytest.raises(FileExistsError):
        generate_plugin_file(
            class_name="SamplePlugin",
            description="Duplicate",
            risk_level="LOW",
            approval_requirement="NONE",
            output_dir=str(tmp_path),
        )
