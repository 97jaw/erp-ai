from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from admin.auth.config import auth_db_enabled
from admin.auth.jwt_tokens import decode_token
from admin.security.rate_limit import (
    RateLimitExceeded,
    check_admin_rate,
    check_api_rate_for_role,
    primary_role_for_limits,
)


class SecurityRateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP login limits (in endpoint) + per-role API limits + admin caps."""

    _SKIP_PREFIXES = ("/health", "/docs", "/openapi.json", "/reports", "/sounds")

    async def dispatch(self, request: Request, call_next) -> Response:
        if not auth_db_enabled():
            return await call_next(request)

        path = request.url.path
        if any(path.startswith(prefix) for prefix in self._SKIP_PREFIXES):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"

        try:
            if path.startswith("/admin"):
                user_key = client_ip
                auth = request.headers.get("authorization", "")
                if auth.lower().startswith("bearer "):
                    token = auth[7:].strip()
                    try:
                        payload = decode_token(token, expected_type="access")
                        user_key = payload.get("sub", client_ip)
                    except ValueError:
                        pass
                check_admin_rate(str(user_key))

            role = self._role_from_request(request)
            if role and not path.startswith("/auth/login"):
                check_api_rate_for_role(role=role, key=str(client_ip))
        except RateLimitExceeded as exc:
            return Response(
                content='{"detail":"' + str(exc.detail).replace('"', '\\"') + '"}',
                status_code=429,
                media_type="application/json",
            )

        return await call_next(request)

    @staticmethod
    def _role_from_request(request: Request) -> str | None:
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            return None
        token = auth[7:].strip()
        if token.count(".") != 2:
            return None
        try:
            payload = decode_token(token, expected_type="access")
        except ValueError:
            return None
        roles = payload.get("roles")
        if isinstance(roles, list) and roles:
            return primary_role_for_limits(roles, is_super_admin=bool(payload.get("sa")))
        return payload.get("role")
