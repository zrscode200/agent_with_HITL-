"""Pytest configuration and shared fixtures."""

import pytest
import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import Mock, AsyncMock

import httpx

from config import Settings
from src.services.semantic_kernel_service import SemanticKernelService
from src.observability.telemetry_service import TelemetryService


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings() -> Settings:
    """Create mock settings for testing."""
    settings = Settings()
    # Override with test values
    settings.azure_openai = None
    settings.openai = None
    return settings


@pytest.fixture
async def mock_http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create a mock HTTP client for testing."""
    async with httpx.AsyncClient() as client:
        yield client


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
async def mock_semantic_kernel_service(
    mock_settings: Settings,
    mock_telemetry_service: TelemetryService,
    mock_http_client: httpx.AsyncClient
) -> AsyncGenerator[SemanticKernelService, None]:
    """Create a mock semantic kernel service for testing."""
    service = SemanticKernelService(
        settings=mock_settings,
        telemetry_service=mock_telemetry_service
    )

    # Mock the initialization to avoid actual AI service setup
    service.initialize_async = AsyncMock()
    service.create_default_agents_async = AsyncMock()

    yield service

    # Cleanup if needed
    if hasattr(service, '_http_client') and service._http_client:
        await service._http_client.aclose()


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