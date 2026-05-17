from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CurrentUser:
    id: int
    file_id: str
    name: str
    language: str
    is_super_admin: bool
    is_active: bool
    roles: tuple[str, ...] = ()
    permissions: frozenset[str] = frozenset()
    department_ids: tuple[int, ...] = ()
    department_codes: tuple[str, ...] = ()

    @classmethod
    def from_record(
        cls,
        row: dict[str, Any],
        *,
        roles: list[str],
        permissions: list[str],
        department_ids: list[int],
        department_codes: list[str],
    ) -> CurrentUser:
        return cls(
            id=int(row["id"]),
            file_id=row["file_id"],
            name=row["name"],
            language=row.get("language") or "en",
            is_super_admin=bool(row.get("is_super_admin")),
            is_active=bool(row.get("is_active", True)),
            roles=tuple(roles),
            permissions=frozenset(permissions),
            department_ids=tuple(department_ids),
            department_codes=tuple(department_codes),
        )

    def has_permission(self, code: str) -> bool:
        if self.is_super_admin:
            return True
        return code in self.permissions

    def has_role(self, name: str) -> bool:
        if self.is_super_admin:
            return True
        return name in self.roles

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "file_id": self.file_id,
            "name": self.name,
            "language": self.language,
            "is_super_admin": self.is_super_admin,
            "roles": list(self.roles),
            "permissions": sorted(self.permissions),
            "departments": list(self.department_codes),
        }
