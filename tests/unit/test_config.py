"""Unit tests for configuration module."""

import pytest
from unittest.mock import patch, MagicMock
import os

from config import Settings, AzureOpenAIConfig, OpenAIConfig


class TestSettings:
    """Test Settings configuration class."""

    def test_settings_creation_with_defaults(self):
        """Test creating settings with default values."""
        settings = Settings()

        assert settings.azure_openai is None
        assert settings.openai is None
        assert settings.agent_platform is not None
        assert settings.observability is not None

    @patch.dict(os.environ, {
        'AZURE_OPENAI_ENDPOINT': 'https://test.openai.azure.com/',
        'AZURE_OPENAI_API_KEY': 'test-azure-key',
        'AZURE_OPENAI_MODEL_ID': 'gpt-4'
    })
    def test_settings_with_azure_openai(self):
        """Test settings with Azure OpenAI configuration."""
        settings = Settings()

        assert settings.azure_openai is not None
        assert settings.azure_openai.endpoint == 'https://test.openai.azure.com/'
        assert settings.azure_openai.api_key == 'test-azure-key'
        assert settings.azure_openai.model_id == 'gpt-4'

    @patch.dict(os.environ, {
        'OPENAI_API_KEY': 'test-openai-key',
        'OPENAI_MODEL_ID': 'gpt-4-turbo'
    })
    def test_settings_with_openai(self):
        """Test settings with OpenAI configuration."""
        settings = Settings()

        assert settings.openai is not None
        assert settings.openai.api_key == 'test-openai-key'
        assert settings.openai.model_id == 'gpt-4-turbo'

    def test_agent_platform_defaults(self):
        """Test agent platform configuration defaults."""
        settings = Settings()

        assert settings.agent_platform.enable_human_in_the_loop is True
        assert settings.agent_platform.approval_timeout_seconds == 1800
        assert settings.agent_platform.max_concurrent_agents == 10

    def test_observability_defaults(self):
        """Test observability configuration defaults."""
        settings = Settings()

        assert settings.observability.enable_telemetry is True
        assert settings.observability.console_exporter_enabled is True
        assert settings.observability.otlp_exporter_enabled is False


class TestAzureOpenAIConfig:
    """Test Azure OpenAI configuration."""

    def test_azure_openai_config_creation(self):
        """Test creating Azure OpenAI configuration."""
        config = AzureOpenAIConfig(
            endpoint="https://test.openai.azure.com/",
            api_key="test-key",
            model_id="gpt-4"
        )

        assert config.endpoint == "https://test.openai.azure.com/"
        assert config.api_key == "test-key"
        assert config.model_id == "gpt-4"
        assert config.api_version == "2024-05-01-preview"

    def test_azure_openai_config_with_custom_version(self):
        """Test Azure OpenAI config with custom API version."""
        config = AzureOpenAIConfig(
            endpoint="https://test.openai.azure.com/",
            api_key="test-key",
            model_id="gpt-4",
            api_version="2024-06-01"
        )

        assert config.api_version == "2024-06-01"


class TestOpenAIConfig:
    """Test OpenAI configuration."""

    def test_openai_config_creation(self):
        """Test creating OpenAI configuration."""
        config = OpenAIConfig(
            api_key="test-key",
            model_id="gpt-4-turbo"
        )

        assert config.api_key == "test-key"
        assert config.model_id == "gpt-4-turbo"

    def test_openai_config_with_custom_model(self):
        """Test OpenAI config with a non-default model id."""
        config = OpenAIConfig(
            api_key="test-key",
            model_id="gpt-4o-mini"
        )

        assert config.model_id == "gpt-4o-mini"
