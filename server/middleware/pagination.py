"""Generic pagination helpers — pure standard-library, no dependencies."""

from __future__ import annotations


def paginate(items: list, page: int = 1, per_page: int = 20) -> dict:
    """Return a pagination envelope for *items*.

    Returns ``{"items": [...], "total": N, "page": P, "pages": M, "per_page": S}``.
    """
    total = len(items)
    pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, pages))
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "items": items[start:end],
        "total": total,
        "page": page,
        "pages": pages,
        "per_page": per_page,
    }


def extract_pagination(params: dict) -> tuple[int, int]:
    """Extract ``(page, per_page)`` from query-parameter dict.

    Handles both raw ``parse_qs`` dicts (values are lists) and
    pre-unwrapped dicts (values are scalars) produced by the router's
    ``_parse_query`` helper.
    """
    raw_page = params.get("page", 1)
    raw_per = params.get("per_page", 20)

    if isinstance(raw_page, list):
        raw_page = raw_page[0]
    if isinstance(raw_per, list):
        raw_per = raw_per[0]

    try:
        page = max(1, int(raw_page))
    except (TypeError, ValueError):
        page = 1

    try:
        per_page = max(1, min(int(raw_per), 100))
    except (TypeError, ValueError):
        per_page = 20

    return page, per_page
