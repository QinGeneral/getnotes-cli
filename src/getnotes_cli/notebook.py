"""知识库 (Notebook/Topic) API 客户端 — 获取知识库列表与知识库内笔记"""

import httpx

from getnotes_cli.auth import AuthToken
from getnotes_cli.config import KNOWLEDGE_API_URL, NOTEBOOKS_API_URL, SUBSCRIBE_NOTEBOOKS_API_URL

# 知识库 API 需要的额外 headers（固定值）
KNOWLEDGE_EXTRA_HEADERS = {
    "X-Appid": "3",
    "X-Av": "1.2.2",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
}


def _build_headers(auth: AuthToken) -> dict[str, str]:
    """构建知识库 API 请求 headers"""
    headers = auth.get_headers()
    headers.update(KNOWLEDGE_EXTRA_HEADERS)
    return headers


def fetch_notebooks(auth: AuthToken, client: httpx.Client | None = None) -> list[dict]:
    """获取用户的所有知识库列表。

    Returns:
        知识库列表，每个元素包含 id, id_alias, name, extend_data, root_dir 等
    """
    _client = client or httpx.Client(timeout=30)
    try:
        headers = _build_headers(auth)
        resp = _client.get(NOTEBOOKS_API_URL, headers=headers, timeout=30)
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
    """获取知识库内的资源列表（分页）。

    Args:
        auth: 认证 token
        topic_id_alias: 知识库别名 ID（如 'aeYz3v0m'）
        directory_id: 目录 ID（root_dir.id）
        page: 页码，从 1 开始
        client: 可复用的 httpx 客户端

    Returns:
        包含 has_next, resources 等字段的 dict
    """
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
        headers = _build_headers(auth)
        resp = _client.get(KNOWLEDGE_API_URL, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("c", {})
    finally:
        if client is None:
            _client.close()


def fetch_subscribed_notebooks(
    auth: AuthToken, client: httpx.Client | None = None
) -> list[dict]:
    """获取用户订阅的知识库列表（不包含自己创建的）。

    Returns:
        订阅知识库列表，结构与 fetch_notebooks 返回一致
    """
    _client = client or httpx.Client(timeout=30)
    try:
        params = {
            "page": 1,
            "size": 200,
            "exclude_mine": "true",
        }
        headers = _build_headers(auth)
        resp = _client.get(
            SUBSCRIBE_NOTEBOOKS_API_URL, headers=headers, params=params, timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("c", {}).get("list", [])
    finally:
        if client is None:
            _client.close()


def add_note_to_notebook(
    auth: AuthToken,
    note_id: str,
    topic_id: int,
    directory_id: int,
    client: httpx.Client | None = None,
) -> dict:
    """将笔记添加到指定知识库。

    Args:
        auth: 认证 token
        note_id: 笔记 ID（字符串）
        topic_id: 知识库整数 ID（notebook["id"]）
        directory_id: 知识库根目录整数 ID（notebook["root_dir"]["id"]）
        client: 可复用的 httpx 客户端

    Returns:
        API 响应 dict，成功时包含 {"h": {"c": 0, ...}, "c": "ok"}

    Raises:
        httpx.HTTPStatusError: 请求失败时
    """
    from getnotes_cli.config import ADD_TO_NOTEBOOK_API_URL

    _client = client or httpx.Client(timeout=30)
    try:
        headers = auth.get_headers()
        payload = {
            "ids": note_id,
            "topic_id": topic_id,
            "directory_id": directory_id,
        }
        resp = _client.post(ADD_TO_NOTEBOOK_API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()
    finally:
        if client is None:
            _client.close()
