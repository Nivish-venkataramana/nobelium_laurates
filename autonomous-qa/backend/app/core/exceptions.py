"""Custom exception hierarchy.

All application-level failures raise one of these so the API layer can
translate them into safe, non-leaky HTTP responses while the full detail
is logged server-side.
"""
from __future__ import annotations


class AppError(Exception):
    """Base class for all application errors."""

    http_status: int = 500
    safe_message: str = "An internal error occurred."

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.safe_message
        super().__init__(self.detail)


class DiscoveryError(AppError):
    http_status = 422
    safe_message = "Application discovery failed."


class SecurityValidationError(AppError):
    http_status = 400
    safe_message = "The request failed security validation."


class AIProviderError(AppError):
    http_status = 502
    safe_message = "The AI provider failed to respond correctly."


class InvalidTestPlanError(AppError):
    http_status = 422
    safe_message = "The generated test plan failed validation."


class ExecutionError(AppError):
    http_status = 500
    safe_message = "Test execution failed."


class HealingError(AppError):
    http_status = 500
    safe_message = "Self-healing failed."


class DatabaseError(AppError):
    http_status = 500
    safe_message = "A database error occurred."


class NotFoundError(AppError):
    http_status = 404
    safe_message = "The requested resource was not found."


class ValidationFailedError(AppError):
    http_status = 422
    safe_message = "Validation failed."
