"""Plugin for HTTP web operations including API calls, web scraping, and data retrieval."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass
import httpx
from semantic_kernel.functions.kernel_function_decorator import kernel_function

from .base_plugin import BasePlugin


@dataclass
class HttpResponse:
    """HTTP response data model."""
    status_code: int
    is_success: bool
    content: str
    headers: Dict[str, str]
    request_url: str
    requested_at: datetime


@dataclass
class ApiResponse:
    """API response data model."""
    data: Any
    status_code: int
    is_success: bool
    content_type: str
    response_size: int
    fetched_at: datetime


@dataclass
class UrlStatus:
    """URL status data model."""
    url: str
    status_code: int
    is_accessible: bool
    response_time_ms: int
    content_type: Optional[str]
    content_length: Optional[int]
    last_checked: datetime
    redirect_url: Optional[str]


class HttpWebPlugin(BasePlugin):
    """
    Plugin for HTTP web operations including API calls, web scraping, and data retrieval.
    Python equivalent of the C# HttpWebPlugin with full feature parity.
    """

    def __init__(self, http_client: Optional[httpx.AsyncClient] = None, logger: Optional[logging.Logger] = None):
        """Initialize the HTTP web plugin."""
        super().__init__(logger)
        self._http_client = http_client or httpx.AsyncClient(timeout=30.0)

    @property
    def plugin_name(self) -> str:
        return "HttpWeb"

    @property
    def plugin_description(self) -> str:
        return "Plugin for HTTP web operations, API calls, and data retrieval"

    @kernel_function(
        name="http_get",
        description="Makes an HTTP GET request to retrieve data from a specified URL"
    )
    async def http_get_async(
        self,
        url: str,
        headers: str = "{}",
        timeout_seconds: int = 30
    ) -> str:
        """Makes an HTTP GET request to the specified URL."""
        function_name = "http_get_async"
        self.log_function_start(function_name, {
            "url": url,
            "headers": headers,
            "timeout_seconds": timeout_seconds
        })

        try:
            self.validate_required_parameter("url", url)

            if not self._is_valid_url(url):
                raise ValueError(f"Invalid URL format: {url}")

            # Parse headers
            headers_dict = {}
            if headers and headers != "{}":
                try:
                    headers_dict = json.loads(headers)
                except json.JSONDecodeError:
                    self._logger.warning(f"Invalid headers JSON: {headers}")

            # Set timeout
            timeout = httpx.Timeout(timeout_seconds)

            # Make request
            response = await self._http_client.get(
                url,
                headers=headers_dict,
                timeout=timeout
            )

            content = response.text
            response_headers = {k: v for k, v in response.headers.items()}

            result_data = HttpResponse(
                status_code=response.status_code,
                is_success=response.is_success,
                content=content,
                headers=response_headers,
                request_url=url,
                requested_at=datetime.utcnow()
            )

            success_response = self.create_success_response(
                function_name,
                result_data.__dict__,
                f"HTTP GET completed with status {response.status_code}"
            )

            self.log_function_complete(function_name, {
                "status_code": response.status_code,
                "content_length": len(content)
            })
            return success_response

        except Exception as ex:
            self.log_function_error(function_name, ex)
            return self.create_error_response(function_name, "Failed to execute HTTP GET request", ex)

    @kernel_function(
        name="http_post",
        description="Makes an HTTP POST request with JSON data to a specified URL"
    )
    async def http_post_async(
        self,
        url: str,
        json_data: str,
        headers: str = "{}",
        timeout_seconds: int = 30
    ) -> str:
        """Makes an HTTP POST request with JSON data."""
        function_name = "http_post_async"
        self.log_function_start(function_name, {
            "url": url,
            "json_data_length": len(json_data) if json_data else 0,
            "headers": headers,
            "timeout_seconds": timeout_seconds
        })

        try:
            self.validate_required_parameter("url", url)
            self.validate_required_parameter("json_data", json_data)

            if not self._is_valid_url(url):
                raise ValueError(f"Invalid URL format: {url}")

            # Parse headers
            headers_dict = {"Content-Type": "application/json"}
            if headers and headers != "{}":
                try:
                    additional_headers = json.loads(headers)
                    headers_dict.update(additional_headers)
                except json.JSONDecodeError:
                    self._logger.warning(f"Invalid headers JSON: {headers}")

            # Validate JSON data
            try:
                json.loads(json_data)  # Validate JSON format
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON data provided")

            # Set timeout
            timeout = httpx.Timeout(timeout_seconds)

            # Make request
            response = await self._http_client.post(
                url,
                content=json_data,
                headers=headers_dict,
                timeout=timeout
            )

            content = response.text
            response_headers = {k: v for k, v in response.headers.items()}

            result_data = HttpResponse(
                status_code=response.status_code,
                is_success=response.is_success,
                content=content,
                headers=response_headers,
                request_url=url,
                requested_at=datetime.utcnow()
            )

            success_response = self.create_success_response(
                function_name,
                result_data.__dict__,
                f"HTTP POST completed with status {response.status_code}"
            )

            self.log_function_complete(function_name, {
                "status_code": response.status_code,
                "content_length": len(content)
            })
            return success_response

        except Exception as ex:
            self.log_function_error(function_name, ex)
            return self.create_error_response(function_name, "Failed to execute HTTP POST request", ex)

    @kernel_function(
        name="fetch_json_data",
        description="Retrieves and parses JSON data from a web API endpoint"
    )
    async def fetch_json_data_async(
        self,
        api_url: str,
        auth_token: Optional[str] = None,
        timeout_seconds: int = 30
    ) -> str:
        """Retrieves and parses JSON data from a web API."""
        function_name = "fetch_json_data_async"
        self.log_function_start(function_name, {
            "api_url": api_url,
            "has_auth_token": bool(auth_token),
            "timeout_seconds": timeout_seconds
        })

        try:
            self.validate_required_parameter("api_url", api_url)

            headers = {"Accept": "application/json"}

            # Add authorization if provided
            if auth_token:
                if auth_token.lower().startswith("bearer "):
                    headers["Authorization"] = auth_token
                else:
                    headers["Authorization"] = f"Bearer {auth_token}"

            # Set timeout
            timeout = httpx.Timeout(timeout_seconds)

            # Make request
            response = await self._http_client.get(
                api_url,
                headers=headers,
                timeout=timeout
            )

            if not response.is_success:
                raise httpx.HTTPStatusError(
                    f"API request failed with status {response.status_code}: {response.text}",
                    request=response.request,
                    response=response
                )

            content = response.text

            # Validate JSON
            try:
                parsed_data = json.loads(content)
            except json.JSONDecodeError:
                raise ValueError("Response is not valid JSON")

            result_data = ApiResponse(
                data=parsed_data,
                status_code=response.status_code,
                is_success=True,
                content_type=response.headers.get("content-type", "application/json"),
                response_size=len(content),
                fetched_at=datetime.utcnow()
            )

            success_response = self.create_success_response(
                function_name,
                {
                    **result_data.__dict__,
                    "data": parsed_data  # Include the parsed data
                },
                "JSON data retrieved and parsed successfully"
            )

            self.log_function_complete(function_name, {
                "status_code": response.status_code,
                "data_size": len(content)
            })
            return success_response

        except Exception as ex:
            self.log_function_error(function_name, ex)
            return self.create_error_response(function_name, "Failed to fetch and parse JSON data", ex)

    @kernel_function(
        name="check_url_status",
        description="Checks if a URL is accessible and returns status information"
    )
    async def check_url_status_async(
        self,
        url: str,
        timeout_seconds: int = 10
    ) -> str:
        """Checks if a URL is accessible and returns basic information about the endpoint."""
        function_name = "check_url_status_async"
        self.log_function_start(function_name, {
            "url": url,
            "timeout_seconds": timeout_seconds
        })

        try:
            self.validate_required_parameter("url", url)

            if not self._is_valid_url(url):
                raise ValueError(f"Invalid URL format: {url}")

            start_time = datetime.utcnow()

            # Set timeout
            timeout = httpx.Timeout(timeout_seconds)

            # Use HEAD request for efficiency
            try:
                response = await self._http_client.head(url, timeout=timeout, follow_redirects=True)
            except httpx.ConnectError:
                # If HEAD fails, try GET with a very small timeout
                try:
                    response = await self._http_client.get(
                        url,
                        timeout=httpx.Timeout(timeout_seconds / 2),
                        follow_redirects=True
                    )
                except Exception:
                    # If both fail, create a failed status
                    response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                    result_data = UrlStatus(
                        url=url,
                        status_code=0,
                        is_accessible=False,
                        response_time_ms=int(response_time),
                        content_type=None,
                        content_length=None,
                        last_checked=datetime.utcnow(),
                        redirect_url=None
                    )

                    return self.create_success_response(
                        function_name,
                        result_data.__dict__,
                        f"URL status check completed: Not accessible"
                    )

            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            result_data = UrlStatus(
                url=url,
                status_code=response.status_code,
                is_accessible=response.is_success,
                response_time_ms=int(response_time),
                content_type=response.headers.get("content-type"),
                content_length=int(response.headers.get("content-length", 0)) if response.headers.get("content-length") else None,
                last_checked=datetime.utcnow(),
                redirect_url=str(response.url) if str(response.url) != url else None
            )

            success_response = self.create_success_response(
                function_name,
                result_data.__dict__,
                f"URL status check completed: {response.status_code}"
            )

            self.log_function_complete(function_name, {
                "status_code": response.status_code,
                "response_time": response_time
            })
            return success_response

        except Exception as ex:
            self.log_function_error(function_name, ex)
            return self.create_error_response(function_name, "Failed to check URL status", ex)

    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format."""
        try:
            # Use httpx's URL parsing
            parsed = httpx.URL(url)
            return parsed.scheme in ["http", "https"] and parsed.host is not None
        except Exception:
            return False

    async def close(self):
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()