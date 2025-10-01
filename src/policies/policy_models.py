"""Data models for policy evaluation and HITL governance."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from src.plugins.tooling_metadata import RiskLevel, ToolDefinition


class PolicyDecision(str, Enum):
    """Outcome of a policy evaluation for a tool invocation."""

    ALLOW = "allow"
    REQUIRE_HUMAN_APPROVAL = "require_human_approval"
    BLOCK = "block"


class ApprovalType(str, Enum):
    """Types of approval requests for different phases."""

    TOOL_EXECUTION = "tool_execution"  # Runtime tool approval
    STRATEGIC_REVIEW = "strategic_review"  # High-level plan review
    TACTICAL_FEASIBILITY = "tactical_feasibility"  # Tool mapping gaps
    PLUGIN_INSTALLATION = "plugin_installation"  # Plugin suggestions
    RUNTIME_DATA = "runtime_data"  # Data requests during execution


@dataclass(slots=True)
class WorkflowPolicy:
    """Policy configuration for a given workflow identifier."""

    workflow_id: str
    automation_threshold: RiskLevel = RiskLevel.MEDIUM
    blocklist: List[str] = field(default_factory=list)
    approval_required: List[str] = field(default_factory=list)
    notes: Optional[str] = None

    def plugin_tool_key(self, plugin_name: str, tool_name: str) -> str:
        return f"{plugin_name}.{tool_name}".lower()

    def is_blocked(self, plugin_name: str, tool_name: str) -> bool:
        return self.plugin_tool_key(plugin_name, tool_name) in {key.lower() for key in self.blocklist}

    def requires_approval(self, plugin_name: str, tool_name: str) -> bool:
        return self.plugin_tool_key(plugin_name, tool_name) in {key.lower() for key in self.approval_required}


@dataclass(slots=True)
class PolicyEvaluation:
    """Details about a policy decision for auditing/telemetry."""

    workflow_id: str
    plugin_name: str
    tool: ToolDefinition
    decision: PolicyDecision
    rationale: str


RISK_ORDER = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}


def compare_risk(level: RiskLevel, threshold: RiskLevel) -> int:
    """Compare two risk levels returning negative/zero/positive like comparator."""
    return RISK_ORDER[level] - RISK_ORDER[threshold]


__all__ = [
    "PolicyDecision",
    "ApprovalType",
    "WorkflowPolicy",
    "PolicyEvaluation",
    "compare_risk",
]
