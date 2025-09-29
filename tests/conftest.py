"""Pytest configuration and shared fixtures."""

from unittest.mock import Mock

import pytest

from config import Settings
from src.observability.telemetry_service import TelemetryService


@pytest.fixture
def mock_settings() -> Settings:
    """Create mock settings for testing."""
    settings = Settings()
    # Override with test values
    settings.azure_openai = None
    settings.openai = None
    return settings


@pytest.fixture
def mock_telemetry_service(mock_settings: Settings) -> TelemetryService:
    """Create a mock telemetry service for testing."""
    service = TelemetryService(mock_settings)
    # Mock the initialization to avoid actual telemetry setup
    service.initialize = Mock()
    service.record_agent_execution = Mock()
    service.record_token_usage = Mock()
    service.record_approval_latency = Mock()
    service.record_error = Mock()
    return service


@pytest.fixture
def sample_document_content() -> str:
    """Sample document content for testing."""
    return """
    This is a sample document for testing purposes.
    It contains some basic text that can be used to test
    document processing functionality.

    The document includes:
    - Multiple paragraphs
    - Basic formatting
    - Sample content for analysis
    """


@pytest.fixture
def sample_document_metadata() -> dict:
    """Sample document metadata for testing."""
    return {
        "id": "test_doc_001",
        "title": "Test Document",
        "type": "policy",
        "created_at": "2025-01-01T00:00:00Z",
        "author": "Test Author"
    }
