from __future__ import annotations


class AppError(RuntimeError):
    """Base typed application error"""

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(AppError):
    """Invalid user or config input"""


class PlatformError(AppError):
    """Unsupported platform or missing permissions"""


class ShellError(AppError):
    """Subprocess execution failed"""


class ServiceError(AppError):
    """Service orchestration failed"""


class SourceBuildRequiredError(AppError):
    """Requested source ref is not available as a release binary"""
