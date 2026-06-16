"""
OOA Core — Universal Entity Resolver
======================================
File    : core/entity_resolver.py
Author  : Lead Backend Developer
Version : 1.0.0

Handles resolution of any entity type from user speech to Odoo record.
Version-agnostic — works with any adapter.

Supported entity types:
    - project    : project.project
    - employee   : hr.employee
    - invoice    : account.move
    - agreement  : agreement (custom)
    - customer   : res.partner
"""

from __future__ import annotations

import logging
import os
from typing import Any

import anthropic

from gateway.model_config import AGENT_MODEL

from core.base_adapter import BaseOdooAdapter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Entity Configuration
# ---------------------------------------------------------------------------

ENTITY_CONFIG = {
    "project": {
        "model"         : "project.project",
        "search_fields" : ["name", "project_name_arabic"],
        "display_fields": [
            "id", "name", "project_name_arabic",
            "wo_ref_no", "agreement_id", "partner_id",
        ],
        "clarify_fields": ["wo_ref_no", "agreement_id", "partner_id"],
        "name_field"    : "name",
    },
    "employee": {
        "model"         : "hr.employee",
        "search_fields" : ["name", "arabic_name"],
        "display_fields": [
            "id", "name", "employee_code",
            "department_id", "job_id",
        ],
        "clarify_fields": ["employee_code", "department_id", "job_id"],
        "name_field"    : "name",
    },
    "invoice": {
        "model"         : "account.move",
        "search_fields" : ["name", "ref"],
        "display_fields": [
            "id", "name", "ref",
            "partner_id", "amount_total", "state",
        ],
        "clarify_fields": ["ref", "partner_id", "amount_total"],
        "name_field"    : "name",
    },
    "agreement": {
        "model"         : "agreement",
        "search_fields" : ["name", "code"],
        "display_fields": [
            "id", "name", "code", "partner_id",
        ],
        "clarify_fields": ["code", "partner_id"],
        "name_field"    : "name",
    },
    "customer": {
        "model"         : "res.partner",
        "search_fields" : ["name", "ref"],
        "display_fields": [
            "id", "name", "ref", "email", "phone",
        ],
        "clarify_fields": ["ref", "email", "phone"],
        "name_field"    : "name",
    },
}

# Languages for clarification messages
CLARIFICATION_MESSAGES = {
    "multiple": {
        "en": "I found {count} {entity_type}s matching your search. Please specify which one:",
        "ar": "وجدت {count} {entity_type} مطابقة لبحثك. يرجى تحديد المقصود:",
        "ur": "آپ کی تلاش سے {count} {entity_type} ملے۔ براہ کرم مطلوبہ بتائیں:",
    },
    "not_found": {
        "en": "I could not find any {entity_type} matching '{search_term}'. Could you provide more details such as {hint}?",
        "ar": "لم أجد أي {entity_type} يطابق '{search_term}'. هل يمكنك تقديم مزيد من التفاصيل مثل {hint}؟",
        "ur": "'{search_term}' سے ملتا جلتا کوئی {entity_type} نہیں ملا۔ براہ کرم {hint} فراہم کریں۔",
    },
}

ENTITY_HINTS = {
    "project" : "WO reference number or agreement ID",
    "employee": "employee code or department name",
    "invoice" : "invoice number or date range",
    "agreement": "agreement code or client name",
    "customer": "customer code or email",
}

ENTITY_HINTS_AR = {
    "project" : "رقم أمر العمل أو معرّف الاتفاقية",
    "employee": "رمز الموظف أو اسم القسم",
    "invoice" : "رقم الفاتورة أو نطاق التاريخ",
    "agreement": "رمز الاتفاقية أو اسم العميل",
    "customer": "رمز العميل أو البريد الإلكتروني",
}

ENTITY_HINTS_UR = {
    "project" : "WO ریفرنس نمبر یا ایگریمنٹ ID",
    "employee": "ملازم کوڈ یا ڈیپارٹمنٹ کا نام",
    "invoice" : "انوائس نمبر یا تاریخ کی حد",
    "agreement": "ایگریمنٹ کوڈ یا کلائنٹ کا نام",
    "customer": "کسٹمر کوڈ یا ای میل",
}


# ---------------------------------------------------------------------------
# Resolution Result
# ---------------------------------------------------------------------------

class ResolutionResult:
    """Typed result from entity resolution."""

    def __init__(
        self,
        resolved_id  : int | None        = None,
        record       : dict | None       = None,
        candidates   : list[dict] | None = None,
        clarification: dict | None       = None,
        error        : str | None        = None,
    ):
        self.resolved_id   = resolved_id
        self.record        = record
        self.candidates    = candidates or []
        self.clarification = clarification
        self.error         = error

    @property
    def is_resolved(self) -> bool:
        return self.resolved_id is not None

    @property
    def needs_clarification(self) -> bool:
        return self.clarification is not None

    @property
    def is_error(self) -> bool:
        return self.error is not None


# ---------------------------------------------------------------------------
# Entity Resolver
# ---------------------------------------------------------------------------

class EntityResolver:
    """
    Universal entity resolver for all Odoo models.

    Resolution strategy:
        1. Direct ID lookup
        2. Search by primary name field
        3. Search by secondary fields (Arabic name, code, ref)
        4. Translate and retry (for Arabic/Urdu input)
        5. If multiple → return clarification
        6. If zero → return not_found clarification
    """

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

    def resolve(
        self,
        entity_type : str,
        search_term : str,
        adapter     : BaseOdooAdapter,
        language    : str = "en",
        direct_id   : int | None = None,
    ) -> ResolutionResult:
        """
        Resolves an entity by name or ID.

        Args:
            entity_type : One of: project, employee, invoice, agreement, customer
            search_term : Name or keyword from user speech
            adapter     : Version adapter for Odoo calls
            language    : User language for clarification messages
            direct_id   : Skip search if ID already known

        Returns:
            ResolutionResult with resolved_id or clarification
        """
        config = ENTITY_CONFIG.get(entity_type)
        if not config:
            return ResolutionResult(error=f"Unknown entity type: {entity_type}")

        # --- Direct ID provided ---
        if direct_id:
            records = self._fetch_by_id(direct_id, config, adapter)
            if records:
                return ResolutionResult(
                    resolved_id = direct_id,
                    record      = records[0],
                )

        if not search_term:
            return ResolutionResult(
                clarification=self._not_found_clarification(
                    entity_type, search_term or "", language, config
                )
            )

        # --- Attempt 1: Primary name field ---
        candidates = self._search(
            search_term, config["name_field"], config, adapter
        )
        result = self._evaluate(
            candidates, entity_type, search_term,
            language, config, original_term=search_term
        )
        if result.is_resolved or result.needs_clarification:
            return result

        # --- Attempt 2: Secondary search fields ---
        for field in config["search_fields"][1:]:
            candidates = self._search(search_term, field, config, adapter)
            result = self._evaluate(
                candidates, entity_type, search_term,
                language, config, original_term=search_term
            )
            if result.is_resolved or result.needs_clarification:
                return result

        # --- Attempt 3: Translate and retry ---
        if language in ("ar", "ur"):
            translated = self._translate(search_term, entity_type)
            if translated and translated.lower() != search_term.lower():
                logger.info(
                    "[EntityResolver] Translated '%s' → '%s'",
                    search_term, translated,
                )
                candidates = self._search(
                    translated, config["name_field"], config, adapter
                )
                result = self._evaluate(
                    candidates, entity_type, search_term,
                    language, config, original_term=search_term
                )
                if result.is_resolved or result.needs_clarification:
                    return result

                # Try keywords from translation
                for keyword in translated.split():
                    if len(keyword) < 3:
                        continue
                    candidates = self._search(
                        keyword, config["name_field"], config, adapter
                    )
                    result = self._evaluate(
                        candidates, entity_type, search_term,
                        language, config, original_term=search_term
                    )
                    if result.is_resolved or result.needs_clarification:
                        return result

        # --- Zero results ---
        return ResolutionResult(
            clarification=self._not_found_clarification(
                entity_type, search_term, language, config
            )
        )

    # -----------------------------------------------------------------------
    # Internal Helpers
    # -----------------------------------------------------------------------

    def _search(
        self,
        term   : str,
        field  : str,
        config : dict,
        adapter: BaseOdooAdapter,
        limit  : int = 5,
    ) -> list[dict]:
        """Searches Odoo for matching records."""
        try:
            return adapter.search_read(
                model  = config["model"],
                domain = [[field, "ilike", term]],
                fields = config["display_fields"],
                limit  = limit,
            )
        except Exception as exc:
            logger.error(
                "[EntityResolver] Search failed on %s.%s: %s",
                config["model"], field, exc,
            )
            return []

    def _fetch_by_id(
        self,
        record_id: int,
        config   : dict,
        adapter  : BaseOdooAdapter,
    ) -> list[dict]:
        """Fetches a single record by ID."""
        try:
            return adapter.search_read(
                model  = config["model"],
                domain = [["id", "=", record_id]],
                fields = config["display_fields"],
                limit  = 1,
            )
        except Exception:
            return []

    def _evaluate(
        self,
        candidates   : list[dict],
        entity_type  : str,
        search_term  : str,
        language     : str,
        config       : dict,
        original_term: str,
    ) -> ResolutionResult:
        """Evaluates search results and returns appropriate result."""

        if len(candidates) == 1:
            return ResolutionResult(
                resolved_id = candidates[0]["id"],
                record      = candidates[0],
            )

        if len(candidates) > 1:
            return ResolutionResult(
                clarification=self._multiple_clarification(
                    candidates, entity_type, language, config, original_term
                )
            )

        return ResolutionResult()  # No match — caller tries next strategy

    def _multiple_clarification(
        self,
        candidates  : list[dict],
        entity_type : str,
        language    : str,
        config      : dict,
        search_term : str,
    ) -> dict:
        """Builds clarification payload for multiple matches."""
        lang = language if language in ("en", "ar", "ur") else "en"

        template = CLARIFICATION_MESSAGES["multiple"][lang]
        message  = template.format(
            count       = len(candidates),
            entity_type = entity_type,
        )

        # Build display lines
        lines = []
        for i, record in enumerate(candidates, 1):
            line = self._format_candidate(record, config, i)
            lines.append(line)

        full_message = message + "\n" + "\n".join(lines)

        return {
            "type"            : f"{entity_type}_selection",
            "entity_type"     : entity_type,
            "candidates"      : candidates,
            "original_message": search_term,
            "message"         : full_message,
            "language"        : lang,
        }

    def _not_found_clarification(
        self,
        entity_type : str,
        search_term : str,
        language    : str,
        config      : dict,
    ) -> dict:
        """Builds clarification payload for zero matches."""
        lang = language if language in ("en", "ar", "ur") else "en"

        hint_map = {
            "en": ENTITY_HINTS,
            "ar": ENTITY_HINTS_AR,
            "ur": ENTITY_HINTS_UR,
        }
        hint = hint_map.get(lang, ENTITY_HINTS).get(entity_type, "more details")

        template = CLARIFICATION_MESSAGES["not_found"][lang]
        message  = template.format(
            entity_type = entity_type,
            search_term = search_term,
            hint        = hint,
        )

        return {
            "type"        : f"{entity_type}_not_found",
            "entity_type" : entity_type,
            "search_term" : search_term,
            "message"     : message,
            "language"    : lang,
            "candidates"  : [],
        }

    def _format_candidate(self, record: dict, config: dict, index: int) -> str:
        """Formats a candidate record for display."""
        name = record.get("name", "Unknown")

        # Clean Arabic name — skip if garbage (less than 3 real chars)
        ar_name = record.get("project_name_arabic", "")
        ar_name = ar_name if ar_name and len(ar_name) > 3 else ""

        line = f"{index}. {name}"
        if ar_name:
            line += f" ({ar_name})"

        # Add clarify fields
        for field in config.get("clarify_fields", []):
            value = record.get(field)
            if not value:
                continue
            # Unwrap [id, name] tuples
            if isinstance(value, list) and len(value) > 1:
                value = value[1]
            if value and str(value) != "False":
                label = field.replace("_id", "").replace("_", " ").title()
                line += f"\n   {label}: {value}"

        return line

    def _translate(self, text: str, entity_type: str) -> str:
        """Translates Arabic/Urdu entity names to English using Claude."""
        try:
            client = anthropic.Anthropic(api_key=self.api_key)
            message = client.messages.create(
                model      = AGENT_MODEL,
                max_tokens = 100,
                messages   = [{
                    "role"   : "user",
                    "content": (
                        f"Translate this UAE {entity_type} name from Arabic "
                        f"to English.\n"
                        f"Rules:\n"
                        f"1. This is a PROPER NOUN — transliterate phonetically\n"
                        f"2. Do NOT translate meanings of place names\n"
                        f"3. Example: زايدية = Zayidia (NOT Zaidism)\n"
                        f"4. Reply with ONLY the English result\n\n"
                        f"Translate: {text}"
                    ),
                }],
            )
            return message.content[0].text.strip()
        except Exception as exc:
            logger.error("[EntityResolver] Translation failed: %s", exc)
            return text
