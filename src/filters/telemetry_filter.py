"""Telemetry filter that integrates with SK's function invocation pipeline."""

import time
import logging
from typing import Optional, Dict, Any, Callable, Awaitable

from semantic_kernel.filters.functions.function_invocation_context import (
    FunctionInvocationContext,
)

from src.observability.telemetry_service import TelemetryService


class TelemetryFilter:
    """
    Telemetry filter that integrates with SK's function invocation pipeline
    to capture metrics and traces for all kernel function calls.
    Python equivalent of the C# TelemetryFilter with full feature parity.
    """

    def __init__(self, telemetry_service: TelemetryService, logger: Optional[logging.Logger] = None):
        """Initialize the telemetry filter."""
        self._telemetry_service = telemetry_service
        self._logger = logger or logging.getLogger(__name__)

    async def on_function_invocation_async(
        self,
        context: FunctionInvocationContext,
        next: Callable[[FunctionInvocationContext], Awaitable[None]],
    ) -> None:
        """Filter function invocations to collect telemetry."""
        function = context.function
        arguments = context.arguments
        function_name = function.name
        plugin_name = function.plugin_name or "Unknown"
        start_time = time.perf_counter()

        # Start telemetry span
        with self._telemetry_service.start_activity(
            f"Function.{plugin_name}.{function_name}",
            {
                "function.name": function_name,
                "function.plugin": plugin_name,
                "function.description": function.description or ""
            }
        ) as span:

            self._logger.debug(f"Starting function invocation: {plugin_name}.{function_name}")

            success = True
            error_message = None

            try:
                # Add input parameters to span
                if span and arguments:
                    for key, value in arguments.items():
                        span.set_attribute(
                            f"function.parameter.{key}",
                            str(value) if value is not None else "null"
                        )

                # Execute the function
                await next(context)
                result = context.result

                # Record success
                if span:
                    span.set_attribute("success", True)

                self._logger.debug(
                    f"Completed function invocation: {plugin_name}.{function_name} "
                    f"in {(time.perf_counter() - start_time) * 1000:.1f}ms"
                )

                # Extract token usage if available in the result
                if result is not None:
                    self._extract_and_record_token_usage(result, plugin_name, function_name)
                return

            except Exception as ex:
                success = False
                error_message = str(ex)

                # Record error in span
                if span:
                    span.set_attribute("success", False)
                    span.set_attribute("error.type", type(ex).__name__)
                    span.set_attribute("error.message", error_message)

                # Record error metric
                self._telemetry_service.record_error(
                    component=f"{plugin_name}.{function_name}",
                    error_type=type(ex).__name__,
                    error_message=error_message,
                    tags={
                        "plugin_name": plugin_name,
                        "function_name": function_name
                    }
                )

                self._logger.error(f"Function invocation failed: {plugin_name}.{function_name}", exc_info=ex)

                # Re-raise the exception to maintain normal error handling
                raise

            finally:
                duration = time.perf_counter() - start_time

                # Record execution metrics
                self._telemetry_service.record_agent_execution(
                    agent_name=f"{plugin_name}.{function_name}",
                    duration_seconds=duration,
                    success=success,
                    tags={
                        "plugin_name": plugin_name,
                        "function_name": function_name,
                        "execution_type": "function"
                    }
                )

                # Add timing to span
                if span:
                    span.set_attribute("function.duration_ms", duration * 1000)

    def _extract_and_record_token_usage(self, result: Any, plugin_name: str, function_name: str) -> None:
        """Extract token usage information from function results if available."""
        try:
            # Check if the result contains token usage information
            # This would typically be available for AI service calls
            if hasattr(result, 'metadata') and result.metadata:
                usage = result.metadata.get('Usage')
                if usage and isinstance(usage, dict):
                    prompt_tokens = self._get_token_count(usage, 'PromptTokens')
                    completion_tokens = self._get_token_count(usage, 'CompletionTokens')
                    total_tokens = self._get_token_count(usage, 'TotalTokens')

                    if total_tokens > 0:
                        model_name = self._get_string_value(usage, 'ModelName') or "unknown"
                        self._telemetry_service.record_token_usage(
                            model_name=model_name,
                            operation=f"{plugin_name}.{function_name}",
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            total_tokens=total_tokens
                        )

            # Alternative: check if result is a structured response with usage info
            elif hasattr(result, '__dict__'):
                result_dict = result.__dict__
                if 'usage' in result_dict or 'token_usage' in result_dict:
                    usage_info = result_dict.get('usage') or result_dict.get('token_usage')
                    if usage_info:
                        self._record_usage_from_dict(usage_info, plugin_name, function_name)

            # For string results that might contain usage information in JSON format
            elif isinstance(result, str):
                self._try_extract_usage_from_string(result, plugin_name, function_name)

        except Exception as ex:
            self._logger.warning(f"Failed to extract token usage from function result: {ex}")

    def _get_token_count(self, usage_dict: Dict[str, Any], key: str) -> int:
        """Get token count from usage dictionary."""
        value = usage_dict.get(key, 0)
        if isinstance(value, int):
            return value
        elif isinstance(value, str) and value.isdigit():
            return int(value)
        return 0

    def _get_string_value(self, usage_dict: Dict[str, Any], key: str) -> Optional[str]:
        """Get string value from usage dictionary."""
        value = usage_dict.get(key)
        return str(value) if value is not None else None

    def _record_usage_from_dict(self, usage_info: Dict[str, Any], plugin_name: str, function_name: str) -> None:
        """Record usage from a dictionary structure."""
        try:
            prompt_tokens = usage_info.get('prompt_tokens', 0)
            completion_tokens = usage_info.get('completion_tokens', 0)
            total_tokens = usage_info.get('total_tokens', prompt_tokens + completion_tokens)
            model_name = usage_info.get('model', 'unknown')

            if total_tokens > 0:
                self._telemetry_service.record_token_usage(
                    model_name=str(model_name),
                    operation=f"{plugin_name}.{function_name}",
                    prompt_tokens=int(prompt_tokens),
                    completion_tokens=int(completion_tokens),
                    total_tokens=int(total_tokens)
                )
        except (ValueError, TypeError) as ex:
            self._logger.debug(f"Could not parse usage info: {ex}")

    def _try_extract_usage_from_string(self, result_str: str, plugin_name: str, function_name: str) -> None:
        """Try to extract usage information from string result."""
        try:
            import json
            import re

            # Look for JSON-like structures containing usage information
            json_pattern = re.compile(r'\{[^{}]*"usage"[^{}]*\}', re.IGNORECASE)
            matches = json_pattern.findall(result_str)

            for match in matches:
                try:
                    usage_data = json.loads(match)
                    if 'usage' in usage_data:
                        self._record_usage_from_dict(usage_data['usage'], plugin_name, function_name)
                        break
                except json.JSONDecodeError:
                    continue

        except Exception:
            # Silently ignore extraction failures
            pass
