from __future__ import annotations

from contextvars import ContextVar

from admin.auth.principal import CurrentUser

_request_user: ContextVar[CurrentUser | None] = ContextVar("ooa_request_user", default=None)


def set_request_user(user: CurrentUser | None) -> None:
    _request_user.set(user)


def get_request_user() -> CurrentUser | None:
    return _request_user.get()


def build_user_context_prompt(user: CurrentUser) -> str:
    perms = ", ".join(sorted(user.permissions)[:12])
    if len(user.permissions) > 12:
        perms += ", …"
    depts = ", ".join(user.department_codes) or "none"
    roles = ", ".join(user.roles) or "none"
    return (
        f"\n\n## Authenticated user\n"
        f"- Name: {user.name} (File ID: {user.file_id})\n"
        f"- Roles: {roles}\n"
        f"- Departments: {depts}\n"
        f"- Language: {user.language}\n"
        f"- Permissions (sample): {perms or 'default'}\n"
        f"Respect data scope: do not expose data outside the user's department "
        f"unless they have full project access.\n"
    )
