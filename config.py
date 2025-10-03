"""Configuration management for the AI Agent Platform."""

import os
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class AzureOpenAIConfig(BaseModel):
    """Azure OpenAI configuration."""
    endpoint: str = Field(..., description="Azure OpenAI endpoint")
    api_key: str = Field(..., description="Azure OpenAI API key")
    model_id: str = Field(default="gpt-4-turbo", description="Default model ID")
    api_version: str = Field(default="2024-05-01-preview", description="API version")


class OpenAIConfig(BaseModel):
    """OpenAI configuration."""
    api_key: str = Field(..., description="OpenAI API key")
    model_id: str = Field(default="gpt-4-turbo", description="Default model ID")


class NotificationConfig(BaseModel):
    """Notification channel configuration."""
    email_enabled: bool = Field(default=False, description="Enable email notifications")
    webhook_enabled: bool = Field(default=False, description="Enable webhook notifications")
    console_enabled: bool = Field(default=True, description="Enable console notifications")
    webhook_url: Optional[str] = Field(default=None, description="Webhook URL")
    smtp_server: Optional[str] = Field(default=None, description="SMTP server")
    smtp_port: int = Field(default=587, description="SMTP port")
    smtp_username: Optional[str] = Field(default=None, description="SMTP username")
    smtp_password: Optional[str] = Field(default=None, description="SMTP password")


class ObservabilityConfig(BaseModel):
    """Observability and telemetry configuration."""
    enable_telemetry: bool = Field(default=True, description="Enable telemetry collection")
    service_name: str = Field(default="AgentPlatform", description="Service name for telemetry")
    service_version: str = Field(default="1.0.0", description="Service version")
    console_exporter_enabled: bool = Field(default=True, description="Enable console exporter")
    otlp_exporter_enabled: bool = Field(default=False, description="Enable OTLP exporter")
    otlp_endpoint: str = Field(default="http://localhost:4317", description="OTLP endpoint")
    azure_monitor_enabled: bool = Field(default=False, description="Enable Azure Monitor")
    azure_monitor_connection_string: Optional[str] = Field(default=None, description="Azure Monitor connection string")


class AgentPlatformConfig(BaseModel):
    """Agent platform configuration."""
    max_concurrent_agents: int = Field(default=10, description="Maximum concurrent agents")
    default_timeout_seconds: int = Field(default=300, description="Default timeout in seconds")
    enable_human_in_the_loop: bool = Field(default=True, description="Enable HITL workflows")
    approval_timeout_seconds: int = Field(default=1800, description="Approval timeout in seconds")
    notifications: NotificationConfig = Field(default_factory=NotificationConfig)
    enable_two_phase_planning: bool = Field(
        default=False,
        description="Enable strategic+tactical planning with capability-aware mapping",
    )
    enable_reactive_executor: bool = Field(
        default=False,
        description="Enable ReAct-style executor that adapts after each observation",
    )


class Settings(BaseSettings):
    """Application settings."""

    # AI Service Configuration
    azure_openai: Optional[AzureOpenAIConfig] = None
    openai: Optional[OpenAIConfig] = None

    # Platform Configuration
    agent_platform: AgentPlatformConfig = Field(default_factory=AgentPlatformConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)

    # Environment variables
    azure_openai_endpoint: Optional[str] = Field(default=None, env="AZURE_OPENAI_ENDPOINT")
    azure_openai_api_key: Optional[str] = Field(default=None, env="AZURE_OPENAI_API_KEY")
    azure_openai_model_id: str = Field(default="gpt-4-turbo", env="AZURE_OPENAI_MODEL_ID")

    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    openai_model_id: str = Field(default="gpt-4-turbo", env="OPENAI_MODEL_ID")

    webhook_url: Optional[str] = Field(default=None, env="WEBHOOK_URL")
    smtp_server: Optional[str] = Field(default=None, env="SMTP_SERVER")
    smtp_port: int = Field(default=587, env="SMTP_PORT")
    smtp_username: Optional[str] = Field(default=None, env="SMTP_USERNAME")
    smtp_password: Optional[str] = Field(default=None, env="SMTP_PASSWORD")

    otel_exporter_otlp_endpoint: str = Field(default="http://localhost:4317", env="OTEL_EXPORTER_OTLP_ENDPOINT")
    applicationinsights_connection_string: Optional[str] = Field(default=None, env="APPLICATIONINSIGHTS_CONNECTION_STRING")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._setup_ai_configs()
        self._setup_notification_config()
        self._setup_observability_config()

    def _setup_ai_configs(self):
        """Set up AI service configurations from environment variables."""
        if self.azure_openai_endpoint and self.azure_openai_api_key:
            self.azure_openai = AzureOpenAIConfig(
                endpoint=self.azure_openai_endpoint,
                api_key=self.azure_openai_api_key,
                model_id=self.azure_openai_model_id
            )

        if self.openai_api_key:
            self.openai = OpenAIConfig(
                api_key=self.openai_api_key,
                model_id=self.openai_model_id
            )

    def _setup_notification_config(self):
        """Set up notification configuration from environment variables."""
        self.agent_platform.notifications = NotificationConfig(
            webhook_enabled=bool(self.webhook_url),
            webhook_url=self.webhook_url,
            email_enabled=bool(self.smtp_server and self.smtp_username),
            smtp_server=self.smtp_server,
            smtp_port=self.smtp_port,
            smtp_username=self.smtp_username,
            smtp_password=self.smtp_password
        )

    def _setup_observability_config(self):
        """Set up observability configuration from environment variables."""
        self.observability = ObservabilityConfig(
            otlp_endpoint=self.otel_exporter_otlp_endpoint,
            azure_monitor_enabled=bool(self.applicationinsights_connection_string),
            azure_monitor_connection_string=self.applicationinsights_connection_string
        )


# Global settings instance
settings = Settings()
