"""
SpeechBridge Custom Exceptions
===============================

Custom exceptions for the framework SpeechBridge.
"""


class SpeechBridgeException(Exception):
    """Basic exception for all SpeechBridge errors"""

    def __init__(self, message: str, details: dict = None):
        """
        Args:
            message: Error message
            details: Additional error details
        """
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self):
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class GPUException(SpeechBridgeException):
    """GPU exception"""
    pass


class ConfigException(SpeechBridgeException):
    """Configuration exception"""
    pass


class ComponentException(SpeechBridgeException):
    """Component-related exception"""
    pass


class ValidationException(SpeechBridgeException):
    """Data validation exception"""
    pass


class PipelineException(SpeechBridgeException):
    """Exception in processing pipeline"""
    pass
