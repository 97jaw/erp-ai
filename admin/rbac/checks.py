from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException

from admin.auth.dependencies import get_current_user
from admin.auth.principal import CurrentUser
from admin.auth.service import get_auth_service


def require_permission(permission_code: str) -> Callable:
    async def _check(user: CurrentUser = Depends(get_current_user)) -> None:
        if user.has_permission(permission_code):
            return
        service = await get_auth_service()
        if service:
            await service.log_permission_denied(
                user_id=user.id,
                permission_code=permission_code,
            )
        raise HTTPException(
            status_code=403,
            detail=f"Missing permission: {permission_code}",
        )

    return _check


def require_any_permission(*permission_codes: str) -> Callable:
    async def _check(user: CurrentUser = Depends(get_current_user)) -> None:
        if any(user.has_permission(code) for code in permission_codes):
            return
        service = await get_auth_service()
        if service:
            await service.log_permission_denied(
                user_id=user.id,
                permission_code=permission_codes[0],
            )
        raise HTTPException(
            status_code=403,
            detail=f"Missing one of: {', '.join(permission_codes)}",
        )

    return _check


def require_role(role_name: str) -> Callable:
    async def _check(user: CurrentUser = Depends(get_current_user)) -> None:
        if user.has_role(role_name):
            return
        raise HTTPException(status_code=403, detail=f"Requires role: {role_name}")

    return _check
