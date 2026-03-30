from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Severity(StrEnum):
    OK = "ok"
    WARN = "warn"
    ERROR = "error"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class HealthCheck:
    key: str
    label: str
    value: str
    severity: Severity = Severity.INFO
    details: str = ""


@dataclass(frozen=True, slots=True)
class HealthReport:
    checks: list[HealthCheck] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(check.severity == Severity.ERROR for check in self.checks)
