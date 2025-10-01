"""Plugin suggestion queue for ops review (no mid-run installation)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass(slots=True)
class PluginSuggestion:
    """Queued plugin installation suggestion."""

    suggested_plugin: str
    required_capability: str
    requested_by_workflow: str
    requested_at: str
    rationale: str
    status: str = "pending"  # pending | approved | rejected | installed
    reviewer_notes: Optional[str] = None


class PluginSuggestionQueue:
    """Queue plugin suggestions for ops review (don't install mid-run)."""

    def __init__(self, store_path: Optional[Path] = None):
        default_path = Path("logs/plugin_suggestions.jsonl")
        self._store_path = store_path or default_path
        os.makedirs(self._store_path.parent, exist_ok=True)

    def suggest_plugin(
        self,
        plugin_name: str,
        capability: str,
        workflow_id: str,
        rationale: str,
    ) -> PluginSuggestion:
        """Queue a plugin suggestion (don't auto-install)."""
        suggestion = PluginSuggestion(
            suggested_plugin=plugin_name,
            required_capability=capability,
            requested_by_workflow=workflow_id,
            requested_at=datetime.utcnow().isoformat(),
            rationale=rationale,
        )

        # Persist to jsonl
        with self._store_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(suggestion)) + "\n")

        return suggestion

    def get_pending_suggestions(self) -> List[PluginSuggestion]:
        """Ops can review pending suggestions."""
        if not self._store_path.exists():
            return []

        suggestions = []
        with self._store_path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    suggestion = PluginSuggestion(**data)
                    if suggestion.status == "pending":
                        suggestions.append(suggestion)

        return suggestions

    def get_all_suggestions(self) -> List[PluginSuggestion]:
        """Get all suggestions regardless of status."""
        if not self._store_path.exists():
            return []

        suggestions = []
        with self._store_path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    suggestions.append(PluginSuggestion(**data))

        return suggestions

    @property
    def path(self) -> Path:
        return self._store_path


__all__ = ["PluginSuggestion", "PluginSuggestionQueue"]
