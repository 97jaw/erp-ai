"""Entity resolution models and decision logic for the reasoning engine."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Literal, Protocol

from gateway.core.context_stack import ContextStack
from gateway.core.project_query_utils import extract_project_name_hint, meaningful_project_words
from gateway.core.strategy_planner import ExecutionStep

logger = logging.getLogger(__name__)

AmbiguityLevel = Literal[
    "no_match",
    "unambiguous",
    "clear_winner",
    "multiple_strong",
    "weak_matches",
]

DecisionAction = Literal[
    "use_match",
    "use_top_with_mention",
    "confirm_top",
    "quick_pick",
    "show_candidates",
    "broaden_or_clarify",
    "search_broader",
]

AMBIGUITY_LEVELS: tuple[AmbiguityLevel, ...] = (
    "no_match",
    "unambiguous",
    "clear_winner",
    "multiple_strong",
    "weak_matches",
)

DECISION_ACTIONS: tuple[DecisionAction, ...] = (
    "use_match",
    "use_top_with_mention",
    "confirm_top",
    "quick_pick",
    "show_candidates",
    "broaden_or_clarify",
    "search_broader",
)


@dataclass
class Match:
    """A candidate entity match with confidence and resolving strategy."""

    entity: dict[str, Any]
    confidence: float
    strategy: str


@dataclass
class ResolutionResult:
    """Aggregated outcome of multi-strategy entity resolution."""

    query: str
    total_matches: int
    confident_matches: list[Match]
    top_match: Match | None
    confidence: float
    ambiguity_level: AmbiguityLevel
    strategies_used: list[str] = field(default_factory=list)
    weak_matches: list[Match] = field(default_factory=list)
    raw_discovery_count: int = 0
    winning_strategy: str | None = None

CONFIDENT_CONFIDENCE_MIN = 0.6
WEAK_CONFIDENCE_MIN = 0.3


@dataclass
class Decision:
    """Recommended handling for a resolution result."""

    action: DecisionAction
    match: Match | None = None
    alternatives: list[Match] = field(default_factory=list)
    note: str | None = None


@dataclass
class StepFailure:
    """Records a failed execution step during orchestration."""

    step: ExecutionStep
    error: Exception | str


class ResolutionStrategy:
    """Decides how to handle entity resolution results based on user role."""

    def decide(self, result: ResolutionResult, context: ContextStack) -> Decision:
        """Return the recommended action for a resolution result."""
        matches = result.confident_matches
        if not matches:
            return Decision(
                action="search_broader",
                note="Try different terms or ask user",
            )

        situation = self._classify_situation(matches)
        aggressive = self._is_aggressive(context)

        if situation == "unambiguous":
            return self._decide_unambiguous(matches[0])
        if situation == "clear_winner":
            return self._decide_clear_winner(matches, aggressive)
        if situation == "multiple_strong":
            return self._decide_multiple_strong(matches, aggressive)
        return self._decide_weak_matches(matches)

    @staticmethod
    def _is_aggressive(context: ContextStack) -> bool:
        """Return True for super admin / aggressive assumption users."""
        return context.user.assumption_level() == "aggressive"

    @staticmethod
    def _entity_name(match: Match) -> str:
        """Return the display name for a matched entity."""
        name = match.entity.get("name")
        return str(name) if name is not None else "unknown"

    @staticmethod
    def _classify_situation(matches: list[Match]) -> str:
        """Classify the resolution outcome for decision routing."""
        if len(matches) == 1 and matches[0].confidence > 0.9:
            return "unambiguous"

        if len(matches) >= 2:
            top, second = matches[0], matches[1]
            if top.confidence > 0.85 and second.confidence < 0.6:
                return "clear_winner"

        if len(matches) >= 3 and all(match.confidence > 0.7 for match in matches[:3]):
            return "multiple_strong"

        return "weak_matches"

    def _decide_unambiguous(self, match: Match) -> Decision:
        name = self._entity_name(match)
        return Decision(
            action="show_candidates",
            alternatives=[match],
            note=f"Please confirm: {name}",
        )

    def _decide_clear_winner(self, matches: list[Match], aggressive: bool) -> Decision:
        del aggressive
        return Decision(
            action="show_candidates",
            alternatives=matches[:5],
            note="Multiple matches found — user must confirm before financial data",
        )

    def _decide_multiple_strong(self, matches: list[Match], aggressive: bool) -> Decision:
        del aggressive
        return Decision(
            action="show_candidates",
            alternatives=matches[:5],
            note="Multiple strong matches — review candidates",
        )

    def _decide_weak_matches(self, matches: list[Match]) -> Decision:
        return Decision(
            action="show_candidates",
            alternatives=matches[:5],
            note="Please confirm which record you mean",
        )


ACRONYM_MAP: dict[str, str] = {
    "ngc": "National Guard",
    "adp": "Abu Dhabi Police",
    "ngn": "National Guard Network",
    "moe": "Ministry of Education",
    "moi": "Ministry of Interior",
    "moh": "Ministry of Health",
    "cd": "Civil Defense",
}

ARABIC_EQUIVALENTS: dict[str, list[str]] = {
    "national guard": ["الحرس الوطني"],
    "abu dhabi police": ["شرطة أبوظبي"],
    "civil defense": ["الدفاع المدني"],
    "ministry of education": ["وزارة التربية"],
}

PROJECT_SEARCH_FIELDS = (
    "id",
    "name",
    "project_name_arabic",
    "wo_ref_no",
    "agreement_id",
    "partner_id",
    "description",
)


class ProjectSearchClient(Protocol):
    """Minimal Odoo project search interface for resolver strategies."""

    async def search_projects(self, domain: list[Any], *, limit: int = 20) -> list[dict[str, Any]]:
        """Search project.project records with an Odoo domain."""


class OdooProjectSearch:
    """Adapter-backed project search for live entity resolution."""

    def __init__(self, adapter: Any) -> None:
        self._adapter = adapter
        self._lock = asyncio.Lock()

    async def search_projects(self, domain: list[Any], *, limit: int = 20) -> list[dict[str, Any]]:
        """Run project.project search via safe_search_read (search + read)."""
        async with self._lock:
            def _call() -> list[dict[str, Any]]:
                return self._adapter.safe_search_read(
                    model="project.project",
                    domain=domain,
                    fields=list(PROJECT_SEARCH_FIELDS),
                    limit=limit,
                )

            return await asyncio.to_thread(_call)


class EntityResolver:
    """Robust entity resolution with multiple parallel strategies."""

    STRATEGY_NAMES: tuple[str, ...] = (
        "exact_phrase_match",
        "all_words_match",
        "any_word_match",
        "fuzzy_match",
        "acronym_match",
        "arabic_english_equivalent",
        "semantic_similarity",
        "description_match",
    )

    def __init__(
        self,
        search: ProjectSearchClient,
        *,
        semantic_client: Any | None = None,
        semantic_model: str = "claude-sonnet-4-20250514",
    ) -> None:
        self._search = search
        self._semantic_client = semantic_client
        self._semantic_model = semantic_model

    async def resolve_project(
        self,
        query: str,
        context: ContextStack,
        min_confidence: float = 0.6,
    ) -> ResolutionResult:
        """Find project(s) matching the query using multiple strategies."""
        normalized_query = query.strip()
        fast_strategies = (
            self._exact_phrase_match,
            self._all_words_match,
            self._any_word_match,
            self._acronym_match,
            self._arabic_english_equivalent,
        )
        slow_strategies = (
            self._fuzzy_match,
            self._semantic_similarity,
            self._description_match,
        )

        all_results: list[list[dict[str, Any]]] = []
        for strategy in fast_strategies:
            all_results.append(await strategy(normalized_query, context))

        merged = self._merge_results(all_results)
        if len(merged) < 3:
            for strategy in slow_strategies:
                all_results.append(await strategy(normalized_query, context))
                merged = self._merge_results(all_results)
                if len(merged) >= 3:
                    break

        scored = self._score_matches(merged, normalized_query)
        confident = [match for match in scored if match.confidence >= min_confidence]
        weak = [
            match
            for match in scored
            if WEAK_CONFIDENCE_MIN <= match.confidence < min_confidence
        ]
        if not confident and not weak and merged:
            salvage = sorted(scored, key=lambda match: -match.confidence)
            if salvage and salvage[0].confidence > 0:
                weak = [salvage[0]]
            else:
                weak = [
                    Match(
                        entity=merged[0],
                        confidence=WEAK_CONFIDENCE_MIN,
                        strategy=str(merged[0].get("_strategy") or "discovery"),
                    ),
                ]
        accessible = self._filter_by_permissions(confident, context)
        weak_accessible = self._filter_by_permissions(weak, context)
        top_match = accessible[0] if accessible else (weak_accessible[0] if weak_accessible else None)
        return ResolutionResult(
            query=normalized_query,
            total_matches=len(merged),
            confident_matches=accessible,
            weak_matches=weak_accessible,
            raw_discovery_count=len(merged),
            top_match=top_match,
            confidence=top_match.confidence if top_match else 0.0,
            winning_strategy=top_match.strategy if top_match else None,
            ambiguity_level=self._calculate_ambiguity(accessible or weak_accessible),
            strategies_used=list(self.STRATEGY_NAMES),
        )

    async def _exact_phrase_match(self, query: str, context: ContextStack) -> list[dict[str, Any]]:
        if not query:
            return []
        return await self._search_with_strategy(
            query,
            [["name", "ilike", query]],
            strategy="exact_phrase_match",
        )

    async def _all_words_match(self, query: str, context: ContextStack) -> list[dict[str, Any]]:
        words = meaningful_project_words(query)
        if not words:
            return []
        domain: list[Any] = [["name", "ilike", word] for word in words]
        if len(words) > 1:
            domain = ["&"] * (len(words) - 1) + domain
        return await self._search_with_strategy(query, domain, strategy="all_words_match")

    async def _any_word_match(self, query: str, context: ContextStack) -> list[dict[str, Any]]:
        words = meaningful_project_words(query)
        if not words:
            return []
        domain: list[Any] = [["name", "ilike", word] for word in words]
        if len(words) > 1:
            domain = ["|"] * (len(words) - 1) + domain
        return await self._search_with_strategy(query, domain, strategy="any_word_match")

    async def _fuzzy_match(self, query: str, context: ContextStack) -> list[dict[str, Any]]:
        candidates = await self._any_word_match(query, context)
        if not candidates:
            return []
        query_lower = query.lower()
        scored: list[tuple[dict[str, Any], float]] = []
        for project in candidates:
            best_ratio = 0.0
            for name_field in self._name_fields_for_scoring(project):
                ratio = SequenceMatcher(None, query_lower, name_field.lower()).ratio()
                best_ratio = max(best_ratio, ratio)
            if best_ratio > 0.5:
                scored.append((project, best_ratio))
        results = [project for project, _ratio in sorted(scored, key=lambda item: -item[1])[:20]]
        return [self._tag_entity(project, "fuzzy_match") for project in results]

    async def _acronym_match(self, query: str, context: ContextStack) -> list[dict[str, Any]]:
        query_lower = query.lower().strip()
        results: list[dict[str, Any]] = []
        expansions: list[str] = []

        if query_lower in ACRONYM_MAP:
            expansions.append(ACRONYM_MAP[query_lower])

        for acronym, expansion in ACRONYM_MAP.items():
            if re.search(rf"\b{re.escape(acronym)}\b", query_lower):
                expansions.append(expansion)
                results.extend(
                    await self._search_with_strategy(
                        query,
                        [["name", "ilike", acronym]],
                        strategy="acronym_match",
                    ),
                )

        for expansion in dict.fromkeys(expansions):
            results.extend(await self._all_words_match(expansion, context))
            results.extend(await self._any_word_match(expansion, context))
        return results

    async def _arabic_english_equivalent(self, query: str, context: ContextStack) -> list[dict[str, Any]]:
        query_lower = query.lower()
        results: list[dict[str, Any]] = []
        for english, arabics in ARABIC_EQUIVALENTS.items():
            if english not in query_lower:
                continue
            for arabic in arabics:
                results.extend(
                    await self._search_with_strategy(
                        query,
                        [["name", "ilike", arabic]],
                        strategy="arabic_english_equivalent",
                    ),
                )
        return results

    async def _semantic_similarity(self, query: str, context: ContextStack) -> list[dict[str, Any]]:
        if self._semantic_client is None or not query:
            return []
        all_projects = await self._search.search_projects([[]], limit=200)
        if not all_projects:
            return []
        prompt = (
            f'Query: "{query}"\n'
            f"Projects: {json.dumps([{'id': p.get('id'), 'name': p.get('name')} for p in all_projects[:50]], ensure_ascii=True)}\n"
            'Return ONLY JSON: {"matches":[project_id,...]}'
        )
        try:
            raw = await self._semantic_client.complete_json(
                model=self._semantic_model,
                prompt=prompt,
                max_tokens=300,
            )
            payload = json.loads(self._extract_json(raw))
            ids = {int(value) for value in payload.get("matches") or []}
        except Exception as exc:
            logger.warning("[EntityResolver] semantic_similarity failed: %s", exc)
            return []
        return [
            self._tag_entity(project, "semantic_similarity")
            for project in all_projects
            if int(project.get("id") or 0) in ids
        ]

    async def _description_match(self, query: str, context: ContextStack) -> list[dict[str, Any]]:
        if not query:
            return []
        domain = [
            "|",
            "|",
            ["description", "ilike", query],
            ["name", "ilike", query],
            ["project_name_arabic", "ilike", query],
        ]
        return await self._search_with_strategy(query, domain, strategy="description_match")

    async def _search_with_strategy(
        self,
        query: str,
        domain: list[Any],
        *,
        strategy: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        projects = await self._search.search_projects(domain, limit=limit)
        return [self._tag_entity(project, strategy) for project in projects]

    @staticmethod
    def _tag_entity(project: dict[str, Any], strategy: str) -> dict[str, Any]:
        tagged = dict(project)
        tagged["_strategy"] = strategy
        return tagged

    @staticmethod
    def _merge_results(result_sets: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
        merged: dict[int, dict[str, Any]] = {}
        for results in result_sets:
            for project in results:
                project_id = int(project.get("id") or 0)
                if project_id <= 0:
                    continue
                existing = merged.get(project_id)
                if existing is None:
                    merged[project_id] = dict(project)
                    continue
                existing_strategies = {
                    existing.get("_strategy"),
                    project.get("_strategy"),
                }
                existing["_strategy"] = "+".join(
                    sorted(strategy for strategy in existing_strategies if strategy),
                )
        return list(merged.values())

    def _score_matches(self, matches: list[dict[str, Any]], query: str) -> list[Match]:
        scoring_queries = self._scoring_queries(query)
        scored: list[Match] = []
        for project in matches:
            confidence = max(
                self._score_entity(project, scoring_query)
                for scoring_query in scoring_queries
            )
            scored.append(
                Match(
                    entity=project,
                    confidence=confidence,
                    strategy=str(project.get("_strategy") or "unknown"),
                ),
            )
        return sorted(scored, key=lambda match: -match.confidence)

    @staticmethod
    def _clean_name_for_scoring(name: str) -> str:
        """Remove numeric or WO-style prefixes that hurt confidence scoring."""
        cleaned = re.sub(r"^[\d\-A-Z]+ - ", "", name or "", count=1)
        return cleaned.strip()

    def _name_fields_for_scoring(self, project: dict[str, Any]) -> list[str]:
        """Collect all name-like fields to score against the user query."""
        raw_fields = [
            project.get("name"),
            project.get("name_clean"),
            project.get("x_project_name"),
            project.get("project_name_arabic"),
        ]
        names: list[str] = []
        for raw in raw_fields:
            if raw in (None, ""):
                continue
            text = str(raw).strip()
            if not text:
                continue
            names.append(text)
            cleaned = self._clean_name_for_scoring(text)
            if cleaned and cleaned not in names:
                names.append(cleaned)
        return names

    def _scoring_queries(self, query: str) -> list[str]:
        queries = [query.strip().lower()]
        hint = extract_project_name_hint(query)
        if hint:
            queries.append(hint.strip().lower())
        query_lower = query.lower()
        for acronym, expansion in ACRONYM_MAP.items():
            if re.search(rf"\b{re.escape(acronym)}\b", query_lower):
                queries.append(expansion.lower())
        if query_lower in ACRONYM_MAP:
            queries.append(ACRONYM_MAP[query_lower].lower())
        return list(dict.fromkeys(queries))

    def _score_entity(self, project: dict[str, Any], query: str) -> float:
        query_lower = query.lower().strip()
        query_words = {word for word in query_lower.split() if word}
        if not query_lower:
            return 0.0

        best = 0.0
        for name_field in self._name_fields_for_scoring(project):
            name_lower = name_field.lower()
            field_score = self._score_name_field(name_lower, query_lower, query_words)
            ratio = SequenceMatcher(None, query_lower, name_lower).ratio()
            best = max(best, field_score, ratio)
        return best

    @staticmethod
    def _score_name_field(name_lower: str, query_lower: str, query_words: set[str]) -> float:
        if name_lower == query_lower:
            return 1.0
        if name_lower.startswith(query_lower):
            return 0.9
        if query_lower in name_lower:
            return 0.85
        if query_words and all(word in name_lower for word in query_words):
            return 0.75
        name_words = {word for word in name_lower.split() if word}
        overlap = len(query_words & name_words) / max(len(query_words), 1)
        return overlap * 0.6

    @staticmethod
    def _calculate_ambiguity(matches: list[Match]) -> AmbiguityLevel:
        if not matches:
            return "no_match"
        if len(matches) == 1:
            return "unambiguous"
        if matches[0].confidence > 0.9 and matches[1].confidence < 0.7:
            return "clear_winner"
        if all(match.confidence > 0.7 for match in matches[:3]):
            return "multiple_strong"
        return "weak_matches"

    @staticmethod
    def _filter_by_permissions(matches: list[Match], context: ContextStack) -> list[Match]:
        if context.user.access_breadth() == "all":
            return matches
        return matches

    @staticmethod
    def _extract_json(raw_response: str) -> str:
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        return cleaned.strip()
