"""Few-shot example loading utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass(slots=True)
class FewShotExample:
    title: str
    task: str
    reasoning: str
    output: str


class FewShotLibrary:
    def __init__(self, examples: Dict[str, List[FewShotExample]]) -> None:
        self._examples = examples

    @classmethod
    def from_json(cls, path: Path) -> "FewShotLibrary":
        data = json.loads(path.read_text())
        mapping: Dict[str, List[FewShotExample]] = {}
        for workflow_id, items in data.get("examples", {}).items():
            mapping[workflow_id] = [
                FewShotExample(
                    title=item.get("title", "Example"),
                    task=item["task"],
                    reasoning=item.get("reasoning", ""),
                    output=item.get("output", ""),
                )
                for item in items
            ]
        return cls(mapping)

    def get(self, workflow_id: str) -> List[FewShotExample]:
        return list(self._examples.get(workflow_id, []))


__all__ = ["FewShotExample", "FewShotLibrary"]
