"""笔记搜索 — 根据关键词搜索笔记"""

import re

from getnotes_cli.auth import AuthToken
from getnotes_cli.openapi_client import OpenAPIClient


class NoteSearcher:
    """笔记搜索器"""

    def __init__(self, token: AuthToken):
        self.token = token

    def search(
        self,
        query: str,
        page: int = 1,
        page_size: int = 10,
    ) -> dict:
        """语义搜索笔记（官方 OpenAPI recall）。

        Args:
            query: 搜索关键词
            page: 兼容参数；官方语义搜索不分页
            page_size: 映射为 top_k（最大 10）

        Returns:
            包含 items, total, has_more 的字典
        """
        with OpenAPIClient(self.token) as client:
            items = client.recall(query, top_k=page_size)
        return {
            "items": items,
            "total": len(items),
            "has_more": False,
            "page": 1,
            "semantic": True,
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
