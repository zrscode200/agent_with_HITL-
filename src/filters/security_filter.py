"""Security filter that validates function inputs and prevents malicious operations."""

import logging
import re
import urllib.parse
from typing import List, Set, Optional, Any, Dict, Callable, Awaitable
from semantic_kernel.functions import KernelFunction
from semantic_kernel.kernel import KernelArguments


class SecurityException(Exception):
    """Exception thrown when security validation fails."""
    pass


class SecurityFilter:
    """
    Security filter that validates function inputs and prevents malicious operations.
    Python equivalent of the C# SecurityFilter with full feature parity.
    """

    # Security patterns to detect potentially malicious content
    MALICIOUS_PATTERNS = [
        re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),
        re.compile(r'javascript:', re.IGNORECASE),
        re.compile(r'on\w+\s*=', re.IGNORECASE),
        re.compile(r'(union\s+select|drop\s+table|delete\s+from|insert\s+into)', re.IGNORECASE),
        re.compile(r'(\.\./|\.\.\|\.\.%2f)', re.IGNORECASE),
        re.compile(r'(eval\s*\(|exec\s*\(|system\s*\()', re.IGNORECASE)
    ]

    # Sensitive information patterns
    SENSITIVE_PATTERNS = [
        re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),  # Credit card numbers
        re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),  # SSN format
        re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),  # Email addresses
        re.compile(r'\b(?:password|pwd|key|secret|token)\s*[:=]\s*[^\s]+', re.IGNORECASE),
        re.compile(r'(api[_-]?key|access[_-]?token|secret[_-]?key)\s*[:=]\s*[^\s]+', re.IGNORECASE)
    ]

    # Restricted function names that require special approval
    RESTRICTED_FUNCTIONS: Set[str] = {
        "delete_file",
        "execute_command",
        "system_call",
        "database_write",
        "send_email",
        "make_payment",
        "create_user",
        "delete_user"
    }

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the security filter."""
        self._logger = logger or logging.getLogger(__name__)

    async def on_function_invocation_async(
        self,
        function: KernelFunction,
        arguments: KernelArguments,
        next_filter: Callable[[KernelFunction, KernelArguments], Awaitable[Any]]
    ) -> Any:
        """Filter function invocations for security validation."""
        function_name = function.name
        plugin_name = function.plugin_name or "Unknown"

        self._logger.debug(f"Security filter: Validating function {plugin_name}.{function_name}")

        try:
            # 1. Validate function is allowed to execute
            self._validate_function_execution(plugin_name, function_name)

            # 2. Validate and sanitize input parameters
            self._validate_parameters(arguments, plugin_name, function_name)

            # 3. Check for restricted operations
            self._check_restricted_operations(function_name, arguments)

            self._logger.debug(f"Security filter: Validation passed for {plugin_name}.{function_name}")

            # Execute the function
            result = await next_filter(function, arguments)

            # 4. Post-execution validation if needed
            await self._validate_result_async(result, plugin_name, function_name)

            return result

        except SecurityException:
            self._logger.warning(
                f"Security filter blocked function execution: {plugin_name}.{function_name}"
            )
            raise
        except Exception as ex:
            self._logger.error(
                f"Security filter error during validation of {plugin_name}.{function_name}: {ex}",
                exc_info=ex
            )
            raise

    def _validate_function_execution(self, plugin_name: str, function_name: str) -> None:
        """Validate whether the function is allowed to execute."""
        # Check if this is a restricted function
        if function_name.lower() in {name.lower() for name in self.RESTRICTED_FUNCTIONS}:
            self._logger.warning(f"Attempted execution of restricted function: {plugin_name}.{function_name}")

            raise SecurityException(
                f"Function {plugin_name}.{function_name} requires special authorization "
                "and cannot be executed directly."
            )

    def _validate_parameters(self, arguments: KernelArguments, plugin_name: str, function_name: str) -> None:
        """Validate and sanitize input parameters."""
        for param_name, param_value in arguments.items():
            if param_value is None:
                continue

            param_str = str(param_value)
            if not param_str.strip():
                continue

            # Check for malicious patterns
            for pattern in self.MALICIOUS_PATTERNS:
                if pattern.search(param_str):
                    self._logger.warning(
                        f"Malicious pattern detected in parameter {param_name} "
                        f"for function {plugin_name}.{function_name}"
                    )

                    raise SecurityException(
                        f"Potentially malicious content detected in parameter '{param_name}'. "
                        "Request blocked for security reasons."
                    )

            # Check for sensitive information
            for pattern in self.SENSITIVE_PATTERNS:
                if pattern.search(param_str):
                    self._logger.warning(
                        f"Sensitive information detected in parameter {param_name} "
                        f"for function {plugin_name}.{function_name}"
                    )
                    # Don't block execution but log the detection

            # Parameter-specific validations
            self._validate_specific_parameter(param_name, param_str, plugin_name, function_name)

    def _validate_specific_parameter(
        self,
        param_name: str,
        param_value: str,
        plugin_name: str,
        function_name: str
    ) -> None:
        """Validate specific parameters based on their names and expected content."""
        param_lower = param_name.lower()

        if param_lower in ["url", "endpoint"]:
            self._validate_url(param_value, plugin_name, function_name)
        elif param_lower == "email":
            self._validate_email(param_value, plugin_name, function_name)
        elif param_lower in ["filepath", "filename"]:
            self._validate_file_path(param_value, plugin_name, function_name)
        elif param_lower in ["command", "script"]:
            self._validate_command(param_value, plugin_name, function_name)

    def _validate_url(self, url: str, plugin_name: str, function_name: str) -> None:
        """Validate URL parameters."""
        try:
            parsed = urllib.parse.urlparse(url)
        except Exception:
            raise SecurityException(f"Invalid URL format in {plugin_name}.{function_name}: {url}")

        # Check scheme
        if parsed.scheme.lower() not in ["http", "https"]:
            raise SecurityException(
                f"URL scheme '{parsed.scheme}' is not allowed in {plugin_name}.{function_name}"
            )

        # Check for localhost and private IP ranges (warning only in development)
        if parsed.hostname:
            hostname_lower = parsed.hostname.lower()
            if (hostname_lower in ["localhost", "127.0.0.1"] or
                hostname_lower.startswith(("192.168.", "10.", "172."))):
                self._logger.warning(
                    f"Access to private/local address attempted: {url} "
                    f"in {plugin_name}.{function_name}"
                )

    def _validate_email(self, email: str, plugin_name: str, function_name: str) -> None:
        """Validate email parameters."""
        if not self._is_valid_email(email):
            raise SecurityException(f"Invalid email format in {plugin_name}.{function_name}: {email}")

    def _validate_file_path(self, file_path: str, plugin_name: str, function_name: str) -> None:
        """Validate file path parameters."""
        # Check for path traversal attempts
        if ".." in file_path or "~" in file_path:
            raise SecurityException(
                f"Potentially unsafe file path in {plugin_name}.{function_name}: {file_path}"
            )

        # Check if absolute path is allowed
        import os.path
        if os.path.isabs(file_path) and not self._is_allowed_path(file_path):
            raise SecurityException(
                f"Absolute file path not allowed in {plugin_name}.{function_name}: {file_path}"
            )

    def _validate_command(self, command: str, plugin_name: str, function_name: str) -> None:
        """Validate command parameters."""
        dangerous_commands = ["rm", "del", "format", "shutdown", "reboot", "kill", "sudo"]

        command_lower = command.lower()
        for dangerous in dangerous_commands:
            if dangerous in command_lower:
                raise SecurityException(
                    f"Potentially dangerous command blocked in {plugin_name}.{function_name}: {command}"
                )

    def _check_restricted_operations(self, function_name: str, arguments: KernelArguments) -> None:
        """Check for operations that require special handling."""
        requires_approval_operations = ["send", "delete", "execute", "install", "uninstall"]

        function_lower = function_name.lower()
        if any(op in function_lower for op in requires_approval_operations):
            self._logger.info(f"Operation requiring approval detected: {function_name}")
            # In a real system, this might queue the operation for approval

    async def _validate_result_async(self, result: Any, plugin_name: str, function_name: str) -> None:
        """Validate the result after function execution."""
        if result is None:
            return

        result_str = str(result)
        if not result_str:
            return

        # Check if result contains sensitive information that shouldn't be logged
        for pattern in self.SENSITIVE_PATTERNS:
            if pattern.search(result_str):
                self._logger.warning(
                    f"Function result contains sensitive information: {plugin_name}.{function_name}"
                )
                # Consider sanitizing or encrypting the result
                break

    def _is_valid_email(self, email: str) -> bool:
        """Validate email format."""
        email_pattern = re.compile(
            r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        )
        return bool(email_pattern.match(email))

    def _is_allowed_path(self, path: str) -> bool:
        """Check if an absolute path is allowed."""
        import os
        import tempfile

        # Define allowed base paths for file operations
        allowed_base_paths = [
            tempfile.gettempdir(),
            os.path.expanduser("~/Documents"),
            # Add other allowed paths as needed
        ]

        return any(path.startswith(base_path) for base_path in allowed_base_paths)