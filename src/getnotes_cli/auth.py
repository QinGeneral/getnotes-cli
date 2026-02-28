"""Auth token 管理 — 缓存与刷新 Bearer token"""

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from getnotes_cli.config import AUTH_CACHE_FILE, CONFIG_DIR, DEFAULT_HEADERS

logger = logging.getLogger(__name__)


@dataclass
class AuthToken:
    """存储 Bearer token 及相关 headers"""
    authorization: str  # "Bearer xxx"
    csrf_token: str = ""  # Xi-Csrf-Token
    extra_headers: dict[str, str] = field(default_factory=dict)
    extracted_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "authorization": self.authorization,
            "csrf_token": self.csrf_token,
            "extra_headers": self.extra_headers,
            "extracted_at": self.extracted_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AuthToken":
        return cls(
            authorization=data["authorization"],
            csrf_token=data.get("csrf_token", ""),
            extra_headers=data.get("extra_headers", {}),
            extracted_at=data.get("extracted_at", 0),
        )

    def is_expired(self, max_age_minutes: float = 25) -> bool:
        """检查 token 是否过期（得到 token 约 30 分钟有效）"""
        age = time.time() - self.extracted_at
        return age > (max_age_minutes * 60)

    def get_headers(self) -> dict[str, str]:
        """生成完整的请求 headers"""
        headers = dict(DEFAULT_HEADERS)
        headers["Authorization"] = self.authorization
        if self.csrf_token:
            headers["Xi-Csrf-Token"] = self.csrf_token
        headers.update(self.extra_headers)
        return headers


def load_cached_token() -> AuthToken | None:
    """从缓存加载 token"""
    if not AUTH_CACHE_FILE.exists():
        return None
    try:
        data = json.loads(AUTH_CACHE_FILE.read_text(encoding="utf-8"))
        return AuthToken.from_dict(data)
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def save_token(token: AuthToken) -> None:
    """保存 token 到缓存"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    AUTH_CACHE_FILE.write_text(
        json.dumps(token.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_or_refresh_token(force_login: bool = False) -> AuthToken:
    """获取有效的 token，过期则自动刷新。

    Args:
        force_login: 强制重新登录

    Returns:
        有效的 AuthToken

    Raises:
        RuntimeError: 无法获取 token
    """
    if not force_login:
        cached = load_cached_token()
        if cached and not cached.is_expired():
            return cached
        if cached and cached.is_expired():
            logger.warning("⚠️  Token 已过期，需要重新登录...")

    # 通过 CDP 获取新 token
    from getnotes_cli.cdp import extract_auth_via_cdp

    headers = extract_auth_via_cdp()
    if not headers or "Authorization" not in headers:
        raise RuntimeError("❌ 登录失败，未能获取 Authorization token")

    token = AuthToken(
        authorization=headers["Authorization"],
        csrf_token=headers.get("Xi-Csrf-Token", ""),
        extra_headers={
            k: v for k, v in headers.items()
            if k not in ("Authorization", "Xi-Csrf-Token")
        },
        extracted_at=time.time(),
    )
    save_token(token)
    return token


def login_with_token(bearer_token: str) -> AuthToken:
    """手动输入 Bearer token 进行登录"""
    if not bearer_token.startswith("Bearer "):
        bearer_token = f"Bearer {bearer_token}"

    token = AuthToken(
        authorization=bearer_token,
        extracted_at=time.time(),
    )
    save_token(token)
    return token
