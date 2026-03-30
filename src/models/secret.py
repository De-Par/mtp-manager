from __future__ import annotations

from dataclasses import asdict, dataclass, field

from errors import ValidationError


@dataclass(slots=True)
class SecretRecord:
    id: int
    raw_secret: str
    enabled: bool = True
    created_at: str = ""
    note: str = ""

    def validate(self) -> None:
        if self.id <= 0:
            raise ValidationError("secret id must be positive")
        if not self.raw_secret or any(char.isspace() for char in self.raw_secret):
            raise ValidationError("raw_secret must be non-empty and whitespace-free")

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return asdict(self)


@dataclass(slots=True)
class UserRecord:
    name: str
    enabled: bool = True
    secrets: list[SecretRecord] = field(default_factory=list)

    def validate(self) -> None:
        if not self.name.strip():
            raise ValidationError("user name must be non-empty")
        for secret in self.secrets:
            secret.validate()

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return {
            "name": self.name,
            "enabled": self.enabled,
            "secrets": [secret.to_dict() for secret in self.secrets],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "UserRecord":
        secrets = [
            SecretRecord(
                id=int(item["id"]),
                raw_secret=str(item["raw_secret"]),
                enabled=bool(item.get("enabled", True)),
                created_at=str(item.get("created_at", "")),
                note=str(item.get("note", "")),
            )
            for item in payload.get("secrets", [])
            if isinstance(item, dict)
        ]
        user = cls(
            name=str(payload.get("name", "")),
            enabled=bool(payload.get("enabled", True)),
            secrets=secrets,
        )
        user.validate()
        return user
