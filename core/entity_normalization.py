from __future__ import annotations

import re


def normalize_client_query(client_name: str) -> list[str]:
    base = re.sub(r"\s+", " ", client_name or "").strip(" \"'.,;:-")
    if not base:
        return []

    variants: list[str] = [base]
    without_unit = re.sub(
        r"\s+(?:CCT|RCC|AA)(?:\s+|$)",
        " ",
        base,
        flags=re.IGNORECASE,
    ).strip(" \"'.,;:-")
    if without_unit and without_unit not in variants:
        variants.append(without_unit)

    without_establishment = re.sub(
        r"\s+ESTABLISHMENT\s*$",
        "",
        without_unit or base,
        flags=re.IGNORECASE,
    ).strip(" \"'.,;:-")
    if without_establishment and without_establishment not in variants:
        variants.append(without_establishment)

    return list(dict.fromkeys(variants))


def client_name_matches_scope(
    candidate: str | None,
    *,
    requested_names: list[str],
    matched_names: list[str] | None = None,
) -> bool:
    if not candidate:
        return False

    candidate_norm = re.sub(r"[.,'\"-]", "", candidate.lower())
    candidate_norm = re.sub(r"\s+", " ", candidate_norm).strip()
    allowed = list(requested_names)
    if matched_names:
        allowed.extend(matched_names)

    for name in allowed:
        name_norm = re.sub(r"[.,'\"-]", "", name.lower())
        name_norm = re.sub(r"\s+", " ", name_norm).strip()
        if not name_norm:
            continue
        if candidate_norm == name_norm:
            return True
        if name_norm in candidate_norm or candidate_norm in name_norm:
            return True
    return False
