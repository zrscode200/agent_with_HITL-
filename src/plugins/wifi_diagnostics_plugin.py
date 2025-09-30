"""Wi-Fi diagnostics plugin for RCA workflows."""

import json
import logging
from pathlib import Path
from typing import Optional

from semantic_kernel.functions.kernel_function_decorator import kernel_function

from src.plugins.base_plugin import BasePlugin
from src.plugins.tooling_metadata import tool_spec, ToolInput, RiskLevel, ApprovalRequirement

DATA_DIR = Path("examples/sim-real-world/network-rca/data")


def _load_json(name: str) -> dict:
    path = DATA_DIR / name
    return json.loads(path.read_text())


class WifiDiagnosticsPlugin(BasePlugin):
    """Provides Wi-Fi telemetry and correlation utilities for RCA agents."""

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        super().__init__(logger)

    @property
    def plugin_name(self) -> str:
        return "WifiDiagnostics"

    @property
    def plugin_description(self) -> str:
        return "Tools for analyzing Wi-Fi alerts, topology, metrics, and change logs"

    @tool_spec(
        description="Summarize active Wi-Fi alerts",
        risk_level=RiskLevel.MEDIUM,
        inputs=[],
        output_description="List of current alerts with severity and remediation hints",
        field_descriptions={
            "id": "Alert identifier",
            "severity": "Alert severity level",
            "message": "Alert description",
            "affected_components": "List of APs/controllers involved",
        },
        sample_output='{"alerts": [{"id": "alert-001", "severity": "critical", "message": "..."}]}',
    )
    @kernel_function(name="list_alerts", description="Return current Wi-Fi alerts")
    async def list_alerts_async(self) -> str:
        alerts = _load_json("alerts.json")
        return self.create_success_response("list_alerts", {"alerts": alerts})

    @tool_spec(
        description="Inspect network topology relationships",
        risk_level=RiskLevel.LOW,
        inputs=[],
        output_description="Topology mapping between controllers and access points",
        field_descriptions={
            "controllers": "List of controllers and connected switches",
            "access_points": "List of APs with locations and controllers",
        },
    )
    @kernel_function(name="inspect_topology", description="Return Wi-Fi topology")
    async def inspect_topology_async(self) -> str:
        topology = _load_json("topology.json")
        return self.create_success_response("inspect_topology", topology)

    @tool_spec(
        description="Retrieve Wi-Fi metrics for APs/SSIDs",
        risk_level=RiskLevel.MEDIUM,
        inputs=[
            ToolInput(name="entity", description="AP ID or SSID name", required=False)
        ],
        output_description="Metrics such as packet loss, SNR, authentication failures",
        field_descriptions={
            "packet_loss": "Packet loss percentage",
            "snr": "Signal-to-noise ratio in dB",
            "client_count": "Number of connected clients",
            "auth_failures": "Authentication failure count",
        },
    )
    @kernel_function(name="fetch_metrics", description="Fetch Wi-Fi metrics")
    async def fetch_metrics_async(self, entity: Optional[str] = None) -> str:
        metrics = _load_json("wifi_metrics.json")
        if entity and entity in metrics:
            payload = {entity: metrics[entity]}
        else:
            payload = metrics
        return self.create_success_response("fetch_metrics", payload)

    @tool_spec(
        description="Correlate recent change log entries",
        risk_level=RiskLevel.MEDIUM,
        approval=ApprovalRequirement.NONE,
        inputs=[
            ToolInput(name="component", description="Component ID to filter", required=False)
        ],
        output_description="List of change records with timestamps",
        field_descriptions={
            "change_id": "Change identifier",
            "component": "Component affected by the change",
            "description": "Change details",
            "timestamp": "When the change occurred",
        },
    )
    @kernel_function(name="check_change_log", description="Return recent change records")
    async def check_change_log_async(self, component: Optional[str] = None) -> str:
        change_log = _load_json("change_log.json")
        if component:
            change_log = [entry for entry in change_log if entry["component"].lower() == component.lower()]
        return self.create_success_response("check_change_log", {"changes": change_log})


__all__ = ["WifiDiagnosticsPlugin"]
