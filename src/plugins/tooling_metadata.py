"""Governance metadata structures for tools and plugins."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Callable, Dict, List, Optional


class RiskLevel(str, Enum):
    """Risk classification for tool execution."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalRequirement(str, Enum):
    """Defines the approval posture required before running a tool."""

    NONE = "none"
    HUMAN = "human"
    POLICY = "policy"


@dataclass(slots=True)
class ToolInput:
    """Describes a single input parameter expected by a tool."""

    name: str
    description: str
    type: str = "string"
    required: bool = True
    schema: Optional[Dict[str, str]] = None


@dataclass(slots=True)
class ToolExample:
    """Example usage that can guide runtime planners or humans."""

    title: str
    prompt: str
    description: Optional[str] = None


@dataclass(slots=True)
class ToolDefinition:
    """Metadata describing an executable tool/function offered by a plugin."""

    name: str
    description: str
    risk_level: RiskLevel = RiskLevel.LOW
    approval: ApprovalRequirement = ApprovalRequirement.NONE
    inputs: List[ToolInput] = field(default_factory=list)
    output_description: Optional[str] = None
    examples: List[ToolExample] = field(default_factory=list)
    tags: Dict[str, str] = field(default_factory=dict)
    field_descriptions: Dict[str, str] = field(default_factory=dict)
    sample_output: Optional[str] = None

    def with_updates(
        self,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> "ToolDefinition":
        """Return a copy with updated name/description when decorators add more context."""
        if name is None and description is None:
            return self
        return replace(
            self,
            name=name or self.name,
            description=description or self.description,
        )


@dataclass(slots=True)
class PluginMetadata:
    """Metadata for a plugin, including the tool manifest."""

    name: str
    description: str
    version: str = "1.0.0"
    owner: Optional[str] = None
    category: Optional[str] = None
    default_risk: RiskLevel = RiskLevel.LOW
    tools: Dict[str, ToolDefinition] = field(default_factory=dict)


TOOL_METADATA_ATTR = "__tool_definition__"


def tool_spec(
    *,
    description: Optional[str] = None,
    risk_level: RiskLevel = RiskLevel.LOW,
    approval: ApprovalRequirement = ApprovalRequirement.NONE,
    inputs: Optional[List[ToolInput]] = None,
    output_description: Optional[str] = None,
    examples: Optional[List[ToolExample]] = None,
    tags: Optional[Dict[str, str]] = None,
    field_descriptions: Optional[Dict[str, str]] = None,
    sample_output: Optional[str] = None,
) -> Callable:
    """Attach governance metadata to a kernel_function."""

    def decorator(func):
        metadata = ToolDefinition(
            name=getattr(func, "__kernel_function_name__", func.__name__),
            description=description or getattr(func, "__doc__", "") or "",
            risk_level=risk_level,
            approval=approval,
            inputs=list(inputs) if inputs else [],
            output_description=output_description,
            examples=list(examples) if examples else [],
            tags=dict(tags) if tags else {},
            field_descriptions=dict(field_descriptions) if field_descriptions else {},
            sample_output=sample_output,
        )
        setattr(func, TOOL_METADATA_ATTR, metadata)
        return func

    return decorator


__all__ = [
    "ApprovalRequirement",
    "PluginMetadata",
    "RiskLevel",
    "ToolDefinition",
    "ToolExample",
    "ToolInput",
    "tool_spec",
    "TOOL_METADATA_ATTR",
]
