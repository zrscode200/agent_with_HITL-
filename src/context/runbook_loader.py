"""Runbook loading utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List


@dataclass(slots=True)
class RunbookSection:
    title: str
    content: str
    priority: int = 0


@dataclass(slots=True)
class Runbook:
    runbook_id: str
    description: str
    sections: List[RunbookSection] = field(default_factory=list)

    def get_sections(self, include: Iterable[str] | None = None) -> List[RunbookSection]:
        if include is None:
            return list(self.sections)
        include_lower = {name.lower() for name in include}
        return [section for section in self.sections if section.title.lower() in include_lower]


class RunbookLibrary:
    def __init__(self, runbooks: Dict[str, Runbook]) -> None:
        self._runbooks = runbooks

    @classmethod
    def from_json(cls, path: Path) -> "RunbookLibrary":
        data = json.loads(path.read_text())
        runbooks: Dict[str, Runbook] = {}
        for item in data.get("runbooks", []):
            sections = [
                RunbookSection(
                    title=section["title"],
                    content=section["content"],
                    priority=section.get("priority", 0),
                )
                for section in item.get("sections", [])
            ]
            runbooks[item["id"]] = Runbook(
                runbook_id=item["id"],
                description=item.get("description", ""),
                sections=sections,
            )
        return cls(runbooks)

    def get(self, runbook_id: str) -> Runbook:
        return self._runbooks[runbook_id]


__all__ = ["RunbookSection", "Runbook", "RunbookLibrary"]
