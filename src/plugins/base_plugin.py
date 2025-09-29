"""Base class for all custom plugins in the agent platform."""

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional, Dict


class BasePlugin(ABC):
    """Base class for all custom plugins in the agent platform."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the base plugin."""
        self._logger = logger or logging.getLogger(self.__class__.__name__)

    @property
    @abstractmethod
    def plugin_name(self) -> str:
        """Get the plugin name for identification purposes."""
        pass

    @property
    @abstractmethod
    def plugin_description(self) -> str:
        """Get the plugin description."""
        pass

    def validate_required_parameter(self, parameter_name: str, value: Any) -> None:
        """Validate input parameters for a function call."""
        if value is None or (isinstance(value, str) and not value.strip()):
            message = f"Required parameter '{parameter_name}' is null or empty"
            self._logger.error(message)
            raise ValueError(message)

    def log_function_start(self, function_name: str, parameters: Optional[Dict[str, Any]] = None) -> None:
        """Log function execution start."""
        self._logger.info(f"Starting {self.plugin_name}.{function_name}")
        if parameters:
            self._logger.debug(f"Function parameters: {json.dumps(parameters, indent=2, default=str)}")

    def log_function_complete(self, function_name: str, result: Optional[Any] = None) -> None:
        """Log function execution completion."""
        self._logger.info(f"Completed {self.plugin_name}.{function_name}")
        if result:
            self._logger.debug(f"Function result: {json.dumps(result, indent=2, default=str)}")

    def log_function_error(self, function_name: str, exception: Exception) -> None:
        """Log function execution error."""
        self._logger.error(
            f"Error in {self.plugin_name}.{function_name}: {str(exception)}",
            exc_info=exception
        )

    def create_error_response(
        self,
        function_name: str,
        error_message: str,
        exception: Optional[Exception] = None
    ) -> str:
        """Create a standardized error response for function failures."""
        error_response = {
            "success": False,
            "function": function_name,
            "plugin": self.plugin_name,
            "error": error_message,
            "timestamp": datetime.utcnow().isoformat(),
            "details": str(exception) if exception else None
        }
        return json.dumps(error_response, indent=2)

    def create_success_response(
        self,
        function_name: str,
        result: Optional[Any] = None,
        message: Optional[str] = None
    ) -> str:
        """Create a standardized success response for function results."""
        success_response = {
            "success": True,
            "function": function_name,
            "plugin": self.plugin_name,
            "message": message or "Operation completed successfully",
            "result": result,
            "timestamp": datetime.utcnow().isoformat()
        }
        return json.dumps(success_response, indent=2, default=str)