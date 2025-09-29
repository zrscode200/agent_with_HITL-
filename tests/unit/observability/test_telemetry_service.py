"""Tests for telemetry helper methods."""

from unittest.mock import MagicMock

from config import Settings
from src.observability.telemetry_service import TelemetryService


def _service() -> TelemetryService:
    settings = Settings()
    service = TelemetryService(settings)
    service._agent_execution_counter = MagicMock()
    service._agent_execution_counter.add = MagicMock()
    service._agent_execution_histogram = MagicMock()
    service._agent_execution_histogram.record = MagicMock()
    return service


def test_record_policy_decision():
    service = _service()
    service.record_policy_decision(
        workflow_id="wf",
        plugin_name="Plugin",
        tool_name="tool",
        decision="require_human_approval",
        risk_level="medium",
        rationale="over threshold",
    )
    service._agent_execution_counter.add.assert_called()


def test_record_approval_event():
    service = _service()
    service.record_approval_event(
        workflow_id="wf",
        plugin_name="Plugin",
        tool_name="tool",
        approved=True,
        reviewer="console",
        request_id="abc",
    )
    service._agent_execution_counter.add.assert_called()
