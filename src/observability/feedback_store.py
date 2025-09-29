"""Simple feedback storage for human notes."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(slots=True)
class FeedbackEntry:
    workflow_id: str
    phase: str
    note: str
    metadata: Dict[str, Any]
    recorded_at: str


class FeedbackStore:
    def __init__(self, path: Optional[Path] = None) -> None:
        default_path = Path("logs/feedback.jsonl")
        self._path = path or default_path
        os.makedirs(self._path.parent, exist_ok=True)

    def record(self, workflow_id: str, phase: str, note: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        entry = FeedbackEntry(
            workflow_id=workflow_id,
            phase=phase,
            note=note,
            metadata=metadata or {},
            recorded_at=datetime.utcnow().isoformat(),
        )
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(entry)) + "\n")

    @property
    def path(self) -> Path:
        return self._path


__all__ = ["FeedbackStore", "FeedbackEntry"]
