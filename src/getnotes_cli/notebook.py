"""Knowledge base API clients.

Official OpenAPI functions are the default. Legacy helpers are kept only for
directory-tree and file-resource downloads that OpenAPI does not expose.
"""

import httpx

from getnotes_cli.auth import AuthToken
from getnotes_cli.config import (
    LEGACY_ADD_TO_NOTEBOOK_API_URL,
    LEGACY_KNOWLEDGE_API_URL,
    LEGACY_NOTEBOOKS_API_URL,
    LEGACY_SUBSCRIBE_NOTEBOOKS_API_URL,
)
from getnotes_cli.openapi_client import OpenAPIClient

# Legacy knowledge API needs these additional browser-like headers.
KNOWLEDGE_EXTRA_HEADERS = {
    "X-Appid": "3",
    "X-Av": "1.2.2",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
}


def fetch_notebooks(auth: AuthToken, client: httpx.Client | None = None) -> list[dict]:
    """Fetch user-created knowledge bases through the official OpenAPI."""
    return _fetch_openapi_topics(auth, subscribed=False)


def fetch_subscribed_notebooks(
    auth: AuthToken, client: httpx.Client | None = None
) -> list[dict]:
    """Fetch subscribed read-only knowledge bases through the official OpenAPI."""
    return _fetch_openapi_topics(auth, subscribed=True)


def _fetch_openapi_topics(auth: AuthToken, *, subscribed: bool) -> list[dict]:
    topics: list[dict] = []
    page = 1
    with OpenAPIClient(auth) as api:
        while True:
            data = (
                api.list_subscribed_knowledge(page=page)
                if subscribed
                else api.list_knowledge(page=page)
            )
            page_topics = _extract_topic_list(data)
            topics.extend(_normalize_topic(t, subscribed=subscribed) for t in page_topics)
            if not _has_next_page(data, page_topics, page):
                break
            page += 1
    return topics


def create_notebook(auth: AuthToken, name: str, description: str = "") -> dict:
    with OpenAPIClient(auth) as api:
        data = api.create_knowledge(name, description)
    return _normalize_topic(data)


def fetch_notebook_notes(
    auth: AuthToken,
    topic_id: str,
    page: int = 1,
    client: OpenAPIClient | None = None,
) -> dict:
    """Fetch one page of notes in a knowledge base through OpenAPI."""
    if client:
        data = client.knowledge_notes(topic_id, page=page)
    else:
        with OpenAPIClient(auth) as api:
            data = api.knowledge_notes(topic_id, page=page)
    notes = data.get("notes") or data.get("list") or data.get("items") or []
    return {
        "notes": notes,
        "has_more": bool(data.get("has_more") or data.get("has_next")),
        "page": data.get("page", page),
        "total": data.get("total") or data.get("total_items"),
    }


def add_note_to_notebook(
    auth: AuthToken,
    note_id: str,
    topic_id: str | int,
    directory_id: int | None = None,
    client: httpx.Client | None = None,
) -> dict:
    """Add a note to a knowledge base through OpenAPI."""
    with OpenAPIClient(auth) as api:
        return api.add_notes_to_knowledge(str(topic_id), [str(note_id)])


def remove_note_from_notebook(
    auth: AuthToken,
    note_id: str,
    topic_id: str | int,
) -> dict:
    """Remove a note from a knowledge base through OpenAPI."""
    with OpenAPIClient(auth) as api:
        return api.remove_notes_from_knowledge(str(topic_id), [str(note_id)])


# ---------------------------------------------------------------------------
# Legacy-only helpers for directory tree / file resources
# ---------------------------------------------------------------------------


def _build_legacy_headers(auth: AuthToken) -> dict[str, str]:
    headers = auth.get_legacy_headers()
    headers.update(KNOWLEDGE_EXTRA_HEADERS)
    return headers


def fetch_legacy_notebooks(auth: AuthToken, client: httpx.Client | None = None) -> list[dict]:
    _client = client or httpx.Client(timeout=30)
    try:
        resp = _client.get(LEGACY_NOTEBOOKS_API_URL, headers=_build_legacy_headers(auth), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("c", [])
    finally:
        if client is None:
            _client.close()


def fetch_notebook_resources(
    auth: AuthToken,
    topic_id_alias: str,
    directory_id: int,
    page: int = 1,
    client: httpx.Client | None = None,
) -> dict:
    _client = client or httpx.Client(timeout=30)
    try:
        params = {
            "topic_id": -1,
            "topic_id_alias": topic_id_alias,
            "directory_id": directory_id,
            "sort": "create_time_desc",
            "resource_type": 0,
            "page": page,
        }
        resp = _client.get(
            LEGACY_KNOWLEDGE_API_URL,
            headers=_build_legacy_headers(auth),
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("c", {})
    finally:
        if client is None:
            _client.close()


def fetch_legacy_subscribed_notebooks(
    auth: AuthToken, client: httpx.Client | None = None
) -> list[dict]:
    _client = client or httpx.Client(timeout=30)
    try:
        params = {
            "page": 1,
            "size": 200,
            "exclude_mine": "true",
        }
        resp = _client.get(
            LEGACY_SUBSCRIBE_NOTEBOOKS_API_URL,
            headers=_build_legacy_headers(auth),
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("c", {}).get("list", [])
    finally:
        if client is None:
            _client.close()


def legacy_add_note_to_notebook(
    auth: AuthToken,
    note_id: str,
    topic_id: int,
    directory_id: int,
    client: httpx.Client | None = None,
) -> dict:
    _client = client or httpx.Client(timeout=30)
    try:
        payload = {
            "ids": note_id,
            "topic_id": topic_id,
            "directory_id": directory_id,
        }
        resp = _client.post(
            LEGACY_ADD_TO_NOTEBOOK_API_URL,
            headers=auth.get_legacy_headers(),
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    finally:
        if client is None:
            _client.close()


def _extract_topic_list(data: dict) -> list[dict]:
    topics = data.get("topics") or data.get("list") or data.get("items") or []
    if isinstance(topics, dict):
        topics = topics.get("topics") or topics.get("list") or []
    return topics if isinstance(topics, list) else []


def _has_next_page(data: dict, items: list[dict], page: int) -> bool:
    if "has_more" in data:
        return bool(data["has_more"])
    if "has_next" in data:
        return bool(data["has_next"])
    total_pages = data.get("total_pages") or data.get("pages")
    if total_pages:
        return page < int(total_pages)
    return False if len(items) == 0 else False


def _normalize_topic(topic: dict, *, subscribed: bool = False) -> dict:
    topic_id = str(
        topic.get("topic_id")
        or topic.get("id_alias")
        or topic.get("id")
        or ""
    )
    stats = topic.get("stats") or {}
    note_count = (
        stats.get("note_count")
        or stats.get("all_resource_count")
        or topic.get("note_count")
        or topic.get("count")
        or 0
    )
    return {
        **topic,
        "id": topic_id,
        "topic_id": topic_id,
        "id_alias": topic_id,
        "name": topic.get("name", "(未命名)"),
        "description": topic.get("description", ""),
        "creator": topic.get("creator") or topic.get("creator_name", ""),
        "subscribed": subscribed,
        "extend_data": {
            **(topic.get("extend_data") or {}),
            "all_resource_count": note_count,
        },
    }
