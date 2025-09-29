"""Service for configuring and managing telemetry using OpenTelemetry."""

import logging
import time
from typing import Optional, Dict, Any
from datetime import datetime
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace.export import ConsoleSpanExporter
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter

from config import Settings


class TelemetryService:
    """
    Service for configuring and managing telemetry using OpenTelemetry.
    Python equivalent of the C# TelemetryService with full feature parity.
    """

    def __init__(self, settings: Settings, logger: Optional[logging.Logger] = None):
        """Initialize the telemetry service."""
        self._settings = settings
        self._logger = logger or logging.getLogger(__name__)

        # OpenTelemetry providers
        self._tracer_provider: Optional[TracerProvider] = None
        self._meter_provider: Optional[MeterProvider] = None

        # Tracer and Meter
        self._tracer = None
        self._meter = None

        # Custom metrics
        self._agent_execution_counter = None
        self._agent_execution_histogram = None
        self._token_usage_counter = None
        self._approval_latency_histogram = None
        self._error_counter = None
        self._active_agents_gauge = None

    def initialize(self) -> None:
        """Initialize OpenTelemetry providers based on configuration."""
        self._logger.info("Initializing telemetry service")

        observability_config = self._settings.observability
        service_name = observability_config.service_name
        service_version = observability_config.service_version

        if not observability_config.enable_telemetry:
            self._logger.info("Telemetry disabled by configuration")
            return

        try:
            self._initialize_tracing(service_name, service_version)
            self._initialize_metrics(service_name, service_version)

            self._logger.info("Telemetry service initialized successfully")

        except Exception as ex:
            self._logger.error(f"Failed to initialize telemetry service: {ex}", exc_info=ex)
            raise

    def record_agent_execution(
        self,
        agent_name: str,
        duration_seconds: float,
        success: bool,
        tags: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record an agent execution event."""
        if not self._agent_execution_counter or not self._agent_execution_histogram:
            return

        base_tags = {
            "agent_name": agent_name,
            "success": str(success).lower()
        }

        # Add custom tags
        if tags:
            for key, value in tags.items():
                base_tags[key] = str(value) if value is not None else "null"

        # Record metrics
        self._agent_execution_counter.add(1, base_tags)
        self._agent_execution_histogram.record(duration_seconds, base_tags)

        self._logger.debug(
            f"Recorded agent execution: {agent_name}, Duration: {duration_seconds:.3f}s, Success: {success}"
        )

    def record_token_usage(
        self,
        model_name: str,
        operation: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int
    ) -> None:
        """Record token usage for AI model calls."""
        if not self._token_usage_counter:
            return

        base_tags = {
            "model_name": model_name,
            "operation": operation
        }

        # Record different token types
        self._token_usage_counter.add(prompt_tokens, {**base_tags, "token_type": "prompt"})
        self._token_usage_counter.add(completion_tokens, {**base_tags, "token_type": "completion"})
        self._token_usage_counter.add(total_tokens, {**base_tags, "token_type": "total"})

        self._logger.debug(
            f"Recorded token usage: {model_name}, Prompt: {prompt_tokens}, "
            f"Completion: {completion_tokens}, Total: {total_tokens}"
        )

    def record_approval_latency(
        self,
        approval_type: str,
        latency_seconds: float,
        approved: bool,
        risk_level: str
    ) -> None:
        """Record human approval latency."""
        if not self._approval_latency_histogram:
            return

        tags = {
            "approval_type": approval_type,
            "approved": str(approved).lower(),
            "risk_level": risk_level.lower()
        }

        self._approval_latency_histogram.record(latency_seconds, tags)

        self._logger.debug(
            f"Recorded approval latency: {approval_type}, Duration: {latency_seconds:.1f}s, "
            f"Approved: {approved}, Risk: {risk_level}"
        )

    def record_error(
        self,
        component: str,
        error_type: str,
        error_message: Optional[str] = None,
        tags: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record an error event."""
        if not self._error_counter:
            return

        base_tags = {
            "component": component,
            "error_type": error_type
        }

        if error_message:
            base_tags["error_message"] = error_message[:100]  # Truncate long messages

        # Add custom tags
        if tags:
            for key, value in tags.items():
                base_tags[key] = str(value) if value is not None else "null"

        self._error_counter.add(1, base_tags)

        self._logger.debug(f"Recorded error: {component}, Type: {error_type}, Message: {error_message}")

    def update_active_agents_count(self, count: int) -> None:
        """Update the active agents count."""
        if self._active_agents_gauge:
            # Note: OpenTelemetry Python gauge implementation may vary
            # This is a placeholder for the actual implementation
            pass

        self._logger.debug(f"Updated active agents count: {count}")

    def start_activity(self, name: str, tags: Optional[Dict[str, Any]] = None):
        """Create a new activity for tracing."""
        if not self._tracer:
            return None

        span = self._tracer.start_span(name)

        if tags:
            for key, value in tags.items():
                span.set_attribute(key, str(value) if value is not None else "null")

        return span

    def record_policy_decision(
        self,
        *,
        workflow_id: str,
        plugin_name: str,
        tool_name: str,
        decision: str,
        risk_level: str,
        rationale: str,
    ) -> None:
        """Record telemetry for a policy decision."""
        self.record_agent_execution(
            agent_name="PolicyEngine",
            duration_seconds=0.0,
            success=decision != "block",
            tags={
                "workflow_id": workflow_id,
                "plugin": plugin_name,
                "tool": tool_name,
                "decision": decision,
                "risk_level": risk_level,
                "rationale": rationale,
            },
        )

    def record_approval_event(
        self,
        *,
        workflow_id: str,
        plugin_name: str,
        tool_name: str,
        approved: bool,
        reviewer: str,
        request_id: str,
    ) -> None:
        """Record telemetry when an approval decision is made."""
        self.record_agent_execution(
            agent_name="ApprovalService",
            duration_seconds=0.0,
            success=approved,
            tags={
                "workflow_id": workflow_id,
                "plugin": plugin_name,
                "tool": tool_name,
                "approved": str(approved).lower(),
                "reviewer": reviewer,
                "request_id": request_id,
            },
        )

    def _initialize_tracing(self, service_name: str, service_version: str) -> None:
        """Initialize distributed tracing."""
        observability_config = self._settings.observability

        # Create resource
        resource = Resource.create({
            SERVICE_NAME: service_name,
            SERVICE_VERSION: service_version,
            "deployment.environment": self._get_environment(),
            "service.instance.id": self._get_instance_id(),
        })

        # Create tracer provider
        self._tracer_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(self._tracer_provider)

        # Configure exporters
        processors = []

        # Console exporter
        if observability_config.console_exporter_enabled:
            console_exporter = ConsoleSpanExporter()
            processors.append(BatchSpanProcessor(console_exporter))

        # OTLP exporter
        if observability_config.otlp_exporter_enabled and observability_config.otlp_endpoint:
            otlp_exporter = OTLPSpanExporter(endpoint=observability_config.otlp_endpoint)
            processors.append(BatchSpanProcessor(otlp_exporter))

        # Azure Monitor exporter
        if (observability_config.azure_monitor_enabled and
            observability_config.azure_monitor_connection_string):
            try:
                from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
                azure_exporter = AzureMonitorTraceExporter(
                    connection_string=observability_config.azure_monitor_connection_string
                )
                processors.append(BatchSpanProcessor(azure_exporter))
            except ImportError:
                self._logger.warning("Azure Monitor exporter not available")

        # Add processors to provider
        for processor in processors:
            self._tracer_provider.add_span_processor(processor)

        # Create tracer
        self._tracer = trace.get_tracer("AgentPlatform", service_version)

    def _initialize_metrics(self, service_name: str, service_version: str) -> None:
        """Initialize metrics collection."""
        observability_config = self._settings.observability

        # Create resource
        resource = Resource.create({
            SERVICE_NAME: service_name,
            SERVICE_VERSION: service_version,
        })

        # Configure exporters
        readers = []

        # Console exporter
        if observability_config.console_exporter_enabled:
            console_reader = PeriodicExportingMetricReader(
                ConsoleMetricExporter(),
                export_interval_millis=60000  # Export every minute
            )
            readers.append(console_reader)

        # OTLP exporter
        if observability_config.otlp_exporter_enabled and observability_config.otlp_endpoint:
            otlp_reader = PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=observability_config.otlp_endpoint),
                export_interval_millis=60000
            )
            readers.append(otlp_reader)

        # Azure Monitor exporter
        if (observability_config.azure_monitor_enabled and
            observability_config.azure_monitor_connection_string):
            try:
                from azure.monitor.opentelemetry.exporter import AzureMonitorMetricExporter
                azure_reader = PeriodicExportingMetricReader(
                    AzureMonitorMetricExporter(
                        connection_string=observability_config.azure_monitor_connection_string
                    ),
                    export_interval_millis=60000
                )
                readers.append(azure_reader)
            except ImportError:
                self._logger.warning("Azure Monitor metrics exporter not available")

        # Create meter provider
        self._meter_provider = MeterProvider(
            resource=resource,
            metric_readers=readers
        )
        metrics.set_meter_provider(self._meter_provider)

        # Create meter
        self._meter = metrics.get_meter("AgentPlatform", service_version)

        # Initialize custom metrics
        self._agent_execution_counter = self._meter.create_counter(
            name="agent_executions_total",
            description="Total number of agent executions",
            unit="1"
        )

        self._agent_execution_histogram = self._meter.create_histogram(
            name="agent_execution_duration_seconds",
            description="Duration of agent executions in seconds",
            unit="s"
        )

        self._token_usage_counter = self._meter.create_counter(
            name="token_usage_total",
            description="Total tokens used by AI models",
            unit="1"
        )

        self._approval_latency_histogram = self._meter.create_histogram(
            name="approval_latency_seconds",
            description="Time taken for human approvals in seconds",
            unit="s"
        )

        self._error_counter = self._meter.create_counter(
            name="errors_total",
            description="Total number of errors encountered",
            unit="1"
        )

        # Note: OpenTelemetry Python gauge creation may vary by version
        # self._active_agents_gauge = self._meter.create_gauge(...)

    def _get_environment(self) -> str:
        """Get the deployment environment."""
        import os
        return os.environ.get("ENVIRONMENT", "development")

    def _get_instance_id(self) -> str:
        """Get the service instance ID."""
        import socket
        return socket.gethostname()

    def shutdown(self) -> None:
        """Shutdown telemetry providers."""
        if self._tracer_provider:
            self._tracer_provider.shutdown()

        if self._meter_provider:
            self._meter_provider.shutdown()

    def __del__(self):
        """Cleanup when object is destroyed."""
        self.shutdown()
