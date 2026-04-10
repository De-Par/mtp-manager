from __future__ import annotations

import secrets
from dataclasses import replace
from datetime import datetime, timezone

from errors import AppError
from infra.storage import JsonStorage
from models.secret import SecretRecord, UserRecord
from paths import ProjectPaths


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class InventoryService:
    def __init__(self, storage: JsonStorage, paths: ProjectPaths) -> None:
        self.storage = storage
        self.paths = paths

    def load_users(self) -> list[UserRecord]:
        payload = self.storage.load_json(self.paths.inventory_file, default={"schema_version": 1, "users": []})
        return [UserRecord.from_dict(item) for item in payload.get("users", []) if isinstance(item, dict)]

    def save_users(self, users: list[UserRecord]) -> None:
        seen_ids: set[int] = set()
        seen_secrets: set[str] = set()
        for user in users:
            user.validate()
            for secret in user.secrets:
                if secret.id in seen_ids:
                    raise AppError(f"duplicate secret id: {secret.id}")
                if secret.raw_secret in seen_secrets:
                    raise AppError(f"duplicate secret value for user: {user.name}")
                seen_ids.add(secret.id)
                seen_secrets.add(secret.raw_secret)
        self.storage.save_json(
            self.paths.inventory_file,
            {"schema_version": 1, "users": [user.to_dict() for user in users]},
        )

    def add_user(self, name: str) -> UserRecord:
        name = name.strip()
        users = self.load_users()
        if any(user.name == name for user in users):
            raise AppError(f"user already exists: {name}")
        user = UserRecord(name=name)
        users.append(user)
        self.save_users(users)
        return user

    def list_user_names(self) -> list[str]:
        return sorted(user.name for user in self.load_users())

    def get_user(self, user_name: str) -> UserRecord:
        for user in self.load_users():
            if user.name == user_name:
                return user
        raise AppError(f"user not found: {user_name}")

    def _next_secret_id(self, users: list[UserRecord]) -> int:
        return max((secret.id for item in users for secret in item.secrets), default=0) + 1

    def _generate_unique_secret(self, users: list[UserRecord], *, ignore_secret_id: int | None = None) -> str:
        existing = {
            secret.raw_secret
            for user in users
            for secret in user.secrets
            if ignore_secret_id is None or secret.id != ignore_secret_id
        }
        while True:
            candidate = secrets.token_hex(16)
            if candidate not in existing:
                return candidate

    def add_secret(self, user_name: str, note: str = "", enabled: bool = True, raw_secret: str | None = None) -> SecretRecord:
        users = self.load_users()
        for index, user in enumerate(users):
            if user.name != user_name:
                continue
            secret = SecretRecord(
                id=self._next_secret_id(users),
                raw_secret=raw_secret or self._generate_unique_secret(users),
                enabled=enabled,
                created_at=utc_now(),
                note=note,
            )
            users[index] = replace(user, secrets=[*user.secrets, secret])
            self.save_users(users)
            return secret
        raise AppError(f"user not found: {user_name}")

    def delete_user(self, user_name: str) -> int:
        users = self.load_users()
        filtered = [user for user in users if user.name != user_name]
        if len(filtered) == len(users):
            raise AppError(f"user not found: {user_name}")
        removed = sum(len(user.secrets) for user in users if user.name == user_name)
        self.save_users(filtered)
        return removed

    def set_user_enabled(self, user_name: str, enabled: bool) -> int:
        users = self.load_users()
        changed = 0
        found = False
        updated: list[UserRecord] = []
        for user in users:
            if user.name == user_name:
                found = True
                updated.append(replace(user, enabled=enabled))
                changed += len(user.secrets)
            else:
                updated.append(user)
        if not found:
            raise AppError(f"user not found: {user_name}")
        self.save_users(updated)
        return changed

    def list_secrets(self) -> list[tuple[UserRecord, SecretRecord]]:
        pairs: list[tuple[UserRecord, SecretRecord]] = []
        for user in self.load_users():
            for secret in user.secrets:
                pairs.append((user, secret))
        return pairs

    def get_secret(self, secret_id: int) -> tuple[UserRecord, SecretRecord]:
        for user, secret in self.list_secrets():
            if secret.id == secret_id:
                return user, secret
        raise AppError(f"secret not found: {secret_id}")

    def set_secret_enabled(self, secret_id: int, enabled: bool) -> None:
        users = self.load_users()
        found = False
        updated_users: list[UserRecord] = []
        for user in users:
            updated_secrets = []
            for secret in user.secrets:
                if secret.id == secret_id:
                    updated_secrets.append(replace(secret, enabled=enabled))
                    found = True
                else:
                    updated_secrets.append(secret)
            updated_users.append(replace(user, secrets=updated_secrets))
        if not found:
            raise AppError(f"secret not found: {secret_id}")
        self.save_users(updated_users)

    def rotate_secret(self, secret_id: int) -> SecretRecord:
        users = self.load_users()
        updated_users: list[UserRecord] = []
        rotated: SecretRecord | None = None
        for user in users:
            updated_secrets = []
            for secret in user.secrets:
                if secret.id == secret_id:
                    replacement = replace(
                        secret,
                        raw_secret=self._generate_unique_secret(users, ignore_secret_id=secret.id),
                        created_at=utc_now(),
                    )
                    updated_secrets.append(replacement)
                    rotated = replacement
                else:
                    updated_secrets.append(secret)
            updated_users.append(replace(user, secrets=updated_secrets))
        if rotated is None:
            raise AppError(f"secret not found: {secret_id}")
        self.save_users(updated_users)
        return rotated

    def rotate_user(self, user_name: str, *, only_enabled: bool = True) -> int:
        users = self.load_users()
        updated_users: list[UserRecord] = []
        changed = 0
        for user in users:
            updated_secrets = []
            for secret in user.secrets:
                should_rotate = user.name == user_name and (secret.enabled or not only_enabled)
                if should_rotate:
                    updated_secrets.append(
                        replace(
                            secret,
                            raw_secret=self._generate_unique_secret(users, ignore_secret_id=secret.id),
                            created_at=utc_now(),
                        )
                    )
                    changed += 1
                else:
                    updated_secrets.append(secret)
            updated_users.append(replace(user, secrets=updated_secrets))
        if changed == 0:
            raise AppError(f"no matching secrets for user: {user_name}")
        self.save_users(updated_users)
        return changed

    def delete_secret(self, secret_id: int) -> None:
        users = self.load_users()
        found = False
        updated_users: list[UserRecord] = []
        for user in users:
            filtered = [secret for secret in user.secrets if secret.id != secret_id]
            if len(filtered) != len(user.secrets):
                found = True
            updated_users.append(replace(user, secrets=filtered))
        if not found:
            raise AppError(f"secret not found: {secret_id}")
        self.save_users(updated_users)

    def enabled_secret_count(self) -> int:
        return sum(1 for user in self.load_users() for secret in user.secrets if user.enabled and secret.enabled)
