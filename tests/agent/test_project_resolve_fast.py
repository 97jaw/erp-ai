from __future__ import annotations

import pytest

from gateway.agent.project_resolve import (
    rank_project_rows,
    score_project_row,
    search_projects_fast,
)


_NG_ROW = {
    "id": 1374,
    "name": "National Guard Health Affairs Central Hospital Riyadh",
    "wo_ref_no": "NG/LG/C&M/01/2020/12",
}
_NG_AIRPORT = {
    "id": 14071,
    "name": "(Airport Project) Design, Construction — National Guard Airport",
    "wo_ref_no": "NG/LG/C&M/09/2024/49",
}
_EMIRATES_ROW = {
    "id": 13098,
    "name": "Emirates National School Boys - Al Ain (Bus Area)",
    "wo_ref_no": "Pending",
}
_GUARD_ROOM = {
    "id": 14435,
    "name": "Maintenance of Guard Room Entrance at Traffic Department",
    "wo_ref_no": "1420240103-32",
}


class _DomainAwareAdapter:
    def safe_search_read(self, model, domain, fields, limit=20, order=None, offset=0):
        assert model == "project.project"
        domain_text = str(domain)
        if "&" in domain_text and "national" in domain_text.lower() and "guard" in domain_text.lower():
            return [_NG_ROW, _NG_AIRPORT]
        if "national guard" in domain_text.lower():
            return [_NG_ROW, _NG_AIRPORT]
        return [_EMIRATES_ROW, _GUARD_ROOM, _NG_AIRPORT]


def test_score_project_row_prefers_phrase_match() -> None:
    ng_score = score_project_row(_NG_ROW, "national guard")
    school_score = score_project_row(_EMIRATES_ROW, "national guard")
    assert ng_score > school_score


def test_rank_project_rows_puts_national_guard_first() -> None:
    ranked = rank_project_rows(
        [_EMIRATES_ROW, _GUARD_ROOM, _NG_ROW, _NG_AIRPORT],
        "national guard",
    )
    top_ids = [row["id"] for row in ranked[:2]]
    assert 1374 in top_ids or 14071 in top_ids
    assert 13098 not in top_ids


@pytest.mark.asyncio
async def test_search_projects_fast_uses_all_words_before_or_noise() -> None:
    rows = await search_projects_fast(_DomainAwareAdapter(), "national guard")
    ids = [row["id"] for row in rows]
    assert 1374 in ids
    assert 14071 in ids
    assert ids.index(13098) > min(ids.index(1374), ids.index(14071))
