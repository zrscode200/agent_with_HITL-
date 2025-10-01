"""Tool mapper for mapping strategic steps to available tools."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from semantic_kernel import Kernel

from src.plugins.tooling_metadata import ToolCapability, ToolDefinition
from src.observability.telemetry_service import TelemetryService


@dataclass(slots=True)
class StrategicStep:
    """High-level step from strategic planning."""

    number: int
    title: str
    required_capability: str
    success_criteria: str
    description: Optional[str] = None


@dataclass(slots=True)
class ToolMapping:
    """Result of mapping a strategic step to tools."""

    strategic_step: StrategicStep
    is_feasible: bool
    matched_tools: List[Tuple[str, str]]  # List of (plugin_name, tool_name) pairs
    required_capability: str
    confidence: float
    mapping_method: str  # "capability_direct" | "fuzzy" | "manual" | "none"
    gap_reason: Optional[str] = None
    suggested_plugin: Optional[str] = None
    requires_review: bool = False  # True for fuzzy/uncertain matches


class ToolMapper:
    """Maps strategic steps to available tools using capability-based matching."""

    def __init__(
        self,
        kernel: Kernel,
        logger: Optional[logging.Logger] = None,
        telemetry: Optional[TelemetryService] = None,
    ):
        self._kernel = kernel
        self._logger = logger or logging.getLogger(self.__class__.__name__)
        self._telemetry = telemetry

        # Build capability registry from plugin metadata (not hardcoded!)
        self._capability_registry = self._build_capability_registry()

    def _build_capability_registry(self) -> Dict[str, List[Tuple[str, str]]]:
        """Build registry from plugin metadata (plugin authors declare capabilities)."""
        registry: Dict[str, List[Tuple[str, str]]] = defaultdict(list)

        # Get all plugins from kernel
        plugins = getattr(self._kernel, "plugins", {}) or {}

        for plugin_name, plugin in plugins.items():
            # Get functions from plugin
            functions = getattr(plugin, "functions", {}) or {}

            for function_name, function in functions.items():
                # Extract metadata if available
                from src.plugins.tooling_metadata import TOOL_METADATA_ATTR

                metadata = getattr(function.metadata, TOOL_METADATA_ATTR, None)
                if metadata and hasattr(metadata, "capabilities") and metadata.capabilities:
                    for capability in metadata.capabilities:
                        capability_key = (
                            capability.value if isinstance(capability, ToolCapability) else str(capability)
                        )
                        registry[capability_key].append((plugin_name, function_name))

        self._logger.info(f"Built capability registry: {len(registry)} capabilities mapped")
        return dict(registry)

    def map_step_to_tools(
        self,
        step: StrategicStep,
        tool_manifest: Dict[str, Dict[str, ToolDefinition]],
    ) -> ToolMapping:
        """Map strategic step to tools using capability-based matching."""

        required_capability = step.required_capability

        # Normalize capability (handle enum or string)
        capability_key = self._normalize_capability(required_capability)

        # Direct capability match
        if capability_key in self._capability_registry:
            matched_tools = self._capability_registry[capability_key]

            if matched_tools:
                self._logger.debug(
                    f"Direct capability match for '{step.title}': {matched_tools}"
                )
                return ToolMapping(
                    strategic_step=step,
                    is_feasible=True,
                    matched_tools=matched_tools,
                    required_capability=required_capability,
                    confidence=1.0,
                    mapping_method="capability_direct",
                )

        # Fuzzy match by description
        fuzzy_result = self._fuzzy_match_tools(step, tool_manifest)

        if fuzzy_result and fuzzy_result["confidence"] > 0.6:
            # Log fuzzy match for compliance
            if self._telemetry:
                self._telemetry.record_agent_execution(
                    agent_name="ToolMapper.FuzzyMatch",
                    duration_seconds=0.0,
                    success=True,
                    tags={
                        "step": step.title,
                        "capability": required_capability,
                        "confidence": str(fuzzy_result["confidence"]),
                        "matched_tools": str(fuzzy_result["tools"]),
                        "method": "fuzzy",
                    },
                )

            self._logger.debug(
                f"Fuzzy match for '{step.title}' (confidence: {fuzzy_result['confidence']:.2f}): "
                f"{fuzzy_result['tools']}"
            )

            return ToolMapping(
                strategic_step=step,
                is_feasible=True,
                matched_tools=fuzzy_result["tools"],
                required_capability=required_capability,
                confidence=fuzzy_result["confidence"],
                mapping_method="fuzzy",
                requires_review=True,  # Flag for potential human override
            )

        # No match: gap detected
        suggested_plugin = self._suggest_plugin_for_capability(required_capability)

        self._logger.warning(
            f"No tools found for step '{step.title}' requiring capability '{required_capability}'"
        )

        return ToolMapping(
            strategic_step=step,
            is_feasible=False,
            matched_tools=[],
            required_capability=required_capability,
            gap_reason=f"No tools found for capability: {required_capability}",
            suggested_plugin=suggested_plugin,
            confidence=0.0,
            mapping_method="none",
        )

    def _normalize_capability(self, capability: str) -> str:
        """Normalize capability string for matching."""
        # Handle enum or string
        if hasattr(capability, "value"):
            return capability.value
        # Convert to lowercase with underscores
        return capability.lower().replace(" ", "_").replace("-", "_")

    def _fuzzy_match_tools(
        self,
        step: StrategicStep,
        tool_manifest: Dict[str, Dict[str, ToolDefinition]],
    ) -> Optional[Dict[str, any]]:
        """Fuzzy match tools by description similarity."""
        best_matches = []
        best_confidence = 0.0

        step_keywords = self._extract_keywords(step.title + " " + (step.description or ""))

        for plugin_name, tools in tool_manifest.items():
            for tool_name, tool_def in tools.items():
                tool_keywords = self._extract_keywords(tool_def.description)

                # Simple keyword overlap similarity
                overlap = len(step_keywords & tool_keywords)
                total = len(step_keywords | tool_keywords)

                if total > 0:
                    confidence = overlap / total

                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_matches = [(plugin_name, tool_name)]
                    elif confidence == best_confidence and confidence > 0:
                        best_matches.append((plugin_name, tool_name))

        if best_matches and best_confidence > 0.3:  # Minimum threshold
            return {
                "tools": best_matches,
                "confidence": best_confidence,
            }

        return None

    def _extract_keywords(self, text: str) -> set:
        """Extract keywords from text for fuzzy matching."""
        # Simple keyword extraction (lowercase, remove common words)
        stop_words = {
            "a",
            "an",
            "and",
            "are",
            "as",
            "at",
            "be",
            "by",
            "for",
            "from",
            "in",
            "is",
            "it",
            "of",
            "on",
            "or",
            "that",
            "the",
            "to",
            "with",
        }

        words = text.lower().split()
        keywords = {word.strip(".,;:!?()[]{}") for word in words if len(word) > 3}
        return keywords - stop_words

    def _suggest_plugin_for_capability(self, capability: str) -> Optional[str]:
        """Suggest a plugin name for a missing capability."""
        # Simple mapping of common capabilities to plugin names
        capability_lower = capability.lower()

        suggestions = {
            "document": "DocumentProcessingPlugin",
            "web": "HttpWebPlugin",
            "http": "HttpWebPlugin",
            "network": "NetworkDiagnosticsPlugin",
            "wifi": "WifiDiagnosticsPlugin",
            "diagnostic": "DiagnosticsPlugin",
            "file": "FileOperationsPlugin",
            "data": "DataAnalysisPlugin",
            "analysis": "DataAnalysisPlugin",
            "communication": "CommunicationPlugin",
            "email": "EmailPlugin",
        }

        for keyword, plugin in suggestions.items():
            if keyword in capability_lower:
                return plugin

        return None

    def get_capability_coverage(self) -> Dict[str, int]:
        """Get statistics on capability coverage."""
        coverage = {}
        for capability, tools in self._capability_registry.items():
            coverage[capability] = len(tools)
        return coverage


__all__ = ["ToolMapper", "ToolMapping", "StrategicStep"]
