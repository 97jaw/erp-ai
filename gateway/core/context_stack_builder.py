"""Assembles a complete ContextStack for each query turn."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Protocol

from admin.auth.principal import CurrentUser
from gateway.core.business_context import BusinessContext
from gateway.core.capability_manifest import CAPABILITY_MANIFEST
from gateway.core.context_stack import (
    ContextStack,
    ConversationContext,
    QualityTargets,
)
from gateway.core.learning_engine import LearningEngine
from gateway.core.temporal_context import TemporalContext
from gateway.core.user_context import UserContext
from gateway.core.working_memory import WorkingMemory

logger = logging.getLogger(__name__)

ROLE_LEVELS: dict[str, int] = {
    "super_admin": 100,
    "admin": 80,
    "top_management": 70,
    "manager": 50,
    "user": 30,
    "auditor": 30,
    "guest": 20,
}


class ChatRequestLike(Protocol):
    """Minimal request shape required to build conversation context."""

    message: str
    session_id: str | None


class ContextStackBuilder:
    """Builds a fresh ContextStack for each incoming query."""

    async def build(self, user: CurrentUser, request: ChatRequestLike) -> ContextStack:
        """Assemble all context components for the current user and request."""
        working_memory = WorkingMemory()
        await self._load_user_patterns(user.id, working_memory)
        if request.session_id:
            from gateway.session_scope import SessionScopeStore

            scope = SessionScopeStore.get(request.session_id)
            if scope.get("confirmed_entities"):
                working_memory.session_facts["confirmed_entities"] = dict(
                    scope["confirmed_entities"],
                )
            if scope.get("project_id"):
                working_memory.session_facts["resolved_project_id"] = int(scope["project_id"])
            if scope.get("last_expense_summary_project_id"):
                working_memory.session_facts["last_expense_summary_project_id"] = int(
                    scope["last_expense_summary_project_id"],
                )
            if scope.get("project_name"):
                working_memory.session_facts["project_name"] = str(scope["project_name"])
            if scope.get("project_id") and not (
                working_memory.session_facts.get("confirmed_entities") or {}
            ).get("project"):
                working_memory.session_facts.setdefault("confirmed_entities", {})
                working_memory.session_facts["confirmed_entities"]["project"] = {
                    "id": int(scope["project_id"]),
                    "name": str(scope.get("project_name") or f"Project {scope['project_id']}"),
                }
            if scope.get("project_id"):
                working_memory.set_active_project(
                    int(scope["project_id"]),
                    str(scope.get("project_name") or f"Project {scope['project_id']}"),
                    confirmed=bool(
                        (scope.get("confirmed_entities") or {}).get("project")
                        or scope.get("last_expense_summary_project_id")
                    ),
                )
            if scope.get("last_turn"):
                working_memory.session_facts["last_turn"] = dict(scope["last_turn"])
        return ContextStack(
            user=self._build_user_context(user),
            conversation=ConversationContext(
                session_id=request.session_id,
                message=request.message,
            ),
            capability_manifest=CAPABILITY_MANIFEST,
            working_memory=working_memory,
            business_context=BusinessContext(),
            temporal_context=TemporalContext.build(),
            quality_targets=QualityTargets(),
        )

    async def _load_user_patterns(self, user_id: int, working_memory: WorkingMemory) -> None:
        try:
            from admin.db.connection import get_admin_db
            from admin.db.repositories.telemetry import TelemetryRepository

            patterns = await TelemetryRepository(get_admin_db()).get_user_patterns(user_id)
            LearningEngine.apply_to_working_memory(working_memory, patterns)
        except RuntimeError:
            return
        except Exception as exc:
            logger.warning("[ContextStackBuilder] could not load user patterns: %s", exc)

    def _build_user_context(self, user: CurrentUser) -> UserContext:
        """Map authenticated user record to intelligence-layer UserContext."""
        primary_role = self._resolve_primary_role(user)
        permissions = set(user.permissions)
        if user.is_super_admin or user.has_permission("odoo.full_access"):
            permissions.add("data.all_projects")

        return UserContext(
            user_id=user.id,
            name=user.name,
            file_id=user.file_id,
            primary_role=primary_role,
            level=self._resolve_level(user, primary_role),
            permissions=permissions,
            primary_department=user.department_codes[0] if user.department_codes else "General",
            departments=list(user.department_codes),
            preferred_language=user.language,
            preferred_currency="AED",
            default_date_range="last_3_months",
            response_style="brief",
            last_login=datetime.now(timezone.utc),
            typical_queries=[],
        )

    def _resolve_primary_role(self, user: CurrentUser) -> str:
        if user.is_super_admin:
            return "super_admin"
        priority = [
            "super_admin",
            "admin",
            "top_management",
            "manager",
            "user",
            "auditor",
            "guest",
        ]
        role_set = set(user.roles)
        for role in priority:
            if role in role_set:
                return role
        return "regular_user"

    def _resolve_level(self, user: CurrentUser, primary_role: str) -> int:
        if user.is_super_admin:
            return ROLE_LEVELS["super_admin"]
        return ROLE_LEVELS.get(primary_role, 30)
