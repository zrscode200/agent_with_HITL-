#!/usr/bin/env python3
"""Scaffold a new plugin using the governance-aware template."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from textwrap import dedent

TEMPLATE = """\
import logging
from typing import Optional
from semantic_kernel.functions.kernel_function_decorator import kernel_function

from src.plugins.base_plugin import BasePlugin
from src.plugins.tooling_metadata import tool_spec, ToolInput, RiskLevel, ApprovalRequirement


class {class_name}(BasePlugin):
    \"\"\"{description}.\"\"\"

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        super().__init__(logger)

    @property
    def plugin_name(self) -> str:
        return "{plugin_name}"

    @property
    def plugin_description(self) -> str:
        return "{description}"

    @tool_spec(
        description="Describe what this tool does",
        risk_level=RiskLevel.{risk_level},
        approval=ApprovalRequirement.{approval_requirement},
        inputs=[
            ToolInput(name="payload", description="Describe required input"),
        ],
        output_description="Describe the output",
        tags={{"category": "custom"}},
    )
    @kernel_function(name="do_work", description="Performs the plugin's main action")
    async def do_work_async(self, payload: str) -> str:
        self.log_function_start("do_work_async", {{"payload": payload}})
        # TODO: implement behaviour
        result = {{"message": "Processed " + payload}}
        self.log_function_complete("do_work_async", result)
        return self.create_success_response("do_work_async", result)


__all__ = ["{class_name}"]
"""


def _snake_case(name: str) -> str:
    return ''.join(['_' + c.lower() if c.isupper() else c for c in name]).lstrip('_')


def generate_plugin_file(
    *,
    class_name: str,
    description: str,
    risk_level: str,
    approval_requirement: str,
    output_dir: str,
) -> Path:
    plugin_name = _snake_case(class_name)
    plugin_path = Path(output_dir) / f"{plugin_name}_plugin.py"

    if plugin_path.exists():
        raise FileExistsError(f"Plugin file already exists: {plugin_path}")

    content = TEMPLATE.format(
        class_name=class_name,
        plugin_name=plugin_name.title().replace('_', ''),
        description=description,
        risk_level=risk_level,
        approval_requirement=approval_requirement,
    )

    os.makedirs(plugin_path.parent, exist_ok=True)
    plugin_path.write_text(dedent(content))
    return plugin_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a new plugin scaffold")
    parser.add_argument("name", help="Plugin class name (e.g., AnalyticsPlugin)")
    parser.add_argument("description", help="Short description of the plugin")
    parser.add_argument("--risk", default="LOW", choices=["LOW", "MEDIUM", "HIGH", "CRITICAL"], help="Default risk level")
    parser.add_argument(
        "--approval",
        default="NONE",
        choices=["NONE", "HUMAN", "POLICY"],
        help="Default approval requirement",
    )
    parser.add_argument("--output", default="src/plugins", help="Output directory")
    args = parser.parse_args()

    try:
        plugin_path = generate_plugin_file(
            class_name=args.name,
            description=args.description,
            risk_level=args.risk,
            approval_requirement=args.approval,
            output_dir=args.output,
        )
    except FileExistsError as exc:  # pragma: no cover - CLI guard
        raise SystemExit(str(exc)) from exc

    print(f"Created plugin scaffold at {plugin_path}")


if __name__ == "__main__":
    main()
