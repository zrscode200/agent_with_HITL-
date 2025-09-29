"""Tests for feedback store."""

from pathlib import Path

from src.observability.feedback_store import FeedbackStore


def test_feedback_store_writes_jsonl(tmp_path: Path):
    store = FeedbackStore(path=tmp_path / "feedback.jsonl")
    store.record("plan-react", "pre", "Investigate latency", metadata={"source": "test"})

    data = (tmp_path / "feedback.jsonl").read_text().strip()
    assert "plan-react" in data
    assert "Investigate latency" in data
