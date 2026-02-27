"""笔记搜索 — 根据关键词搜索笔记"""

import re

import httpx

from getnotes_cli.auth import AuthToken
from getnotes_cli.config import SEARCH_API_URL


class NoteSearcher:
    """笔记搜索器"""

    def __init__(self, token: AuthToken):
        self.token = token
        self.client = httpx.Client(timeout=30)

    def search(
        self,
        query: str,
        page: int = 1,
        page_size: int = 10,
    ) -> dict:
        """搜索笔记

        Args:
            query: 搜索关键词
            page: 页码（从 1 开始）
            page_size: 每页数量

        Returns:
            包含 items, total, has_more 的字典
        """
        params = {
            "page": page,
            "page_size": page_size,
            "query": query,
        }
        headers = self.token.get_headers()
        resp = self.client.get(
            SEARCH_API_URL,
            headers=headers,
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        content = data.get("c", {})
        return {
            "items": content.get("items", []),
            "total": content.get("total", 0),
            "has_more": content.get("has_more", False),
        }

    @staticmethod
    def strip_highlight(text: str) -> str:
        """移除高亮标签 <hl>...</hl>，保留内部文本"""
        return re.sub(r"</?hl>", "", text)

    @staticmethod
    def extract_highlight(text: str) -> str:
        """提取高亮文本片段，用于展示"""
        text = text.replace("\\n", "\n").strip()
        # 移除 hl 标签
        clean = re.sub(r"</?hl>", "", text)
        # 截断过长内容
        if len(clean) > 120:
            clean = clean[:120] + "..."
        return clean
