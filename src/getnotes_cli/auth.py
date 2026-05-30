"""Auth credential management for official OpenAPI and legacy-only flows."""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from getnotes_cli.config import (
    AUTH_CACHE_FILE,
    CONFIG_DIR,
    DEFAULT_HEADERS,
    LEGACY_AUTH_CACHE_FILE,
)

logger = logging.getLogger(__name__)

OFFICIAL_CONFIG_CANDIDATES = (
    Path.home() / ".getnote" / "config.json",
    Path.home() / ".config" / "getnote" / "config.json",
)


@dataclass
class AuthToken:
    """Stores official OpenAPI credentials, or legacy Bearer headers."""

    api_key: str = ""
    client_id: str = ""
    authorization: str = ""
    csrf_token: str = ""
    extra_headers: dict[str, str] = field(default_factory=dict)
    extracted_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "api_key": self.api_key,
            "client_id": self.client_id,
            "authorization": self.authorization,
            "csrf_token": self.csrf_token,
            "extra_headers": self.extra_headers,
            "extracted_at": self.extracted_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuthToken":
        return cls(
            api_key=data.get("api_key", ""),
            client_id=data.get("client_id", ""),
            authorization=data.get("authorization", ""),
            csrf_token=data.get("csrf_token", ""),
            extra_headers=data.get("extra_headers", {}),
            extracted_at=data.get("extracted_at", 0),
        )

    @property
    def is_openapi(self) -> bool:
        return bool(self.api_key and self.client_id)

    @property
    def is_legacy(self) -> bool:
        return bool(self.authorization)

    def is_expired(self, max_age_minutes: float = 25) -> bool:
        """OpenAPI credentials do not expire; legacy Bearer headers do."""
        if self.is_openapi and not self.is_legacy:
            return False
        age = time.time() - self.extracted_at
        return age > (max_age_minutes * 60)

    def get_headers(self) -> dict[str, str]:
        """Generate headers for the official OpenAPI or a legacy request."""
        if self.is_openapi:
            return {
                "Authorization": self.api_key,
                "X-Client-ID": self.client_id,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        return self.get_legacy_headers()

    def get_legacy_headers(self) -> dict[str, str]:
        """Generate legacy Web API headers."""
        headers = dict(DEFAULT_HEADERS)
        if self.authorization:
            headers["Authorization"] = self.authorization
        if self.csrf_token:
            headers["Xi-Csrf-Token"] = self.csrf_token
        headers.update(self.extra_headers)
        return headers


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def load_cached_token() -> AuthToken | None:
    """Load saved official OpenAPI credentials."""
    data = _read_json(AUTH_CACHE_FILE)
    if not data:
        return None
    token = AuthToken.from_dict(data)
    return token if token.is_openapi or token.is_legacy else None


def save_token(token: AuthToken) -> None:
    """Persist official OpenAPI credentials."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    AUTH_CACHE_FILE.write_text(
        json.dumps(token.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_cached_legacy_token() -> AuthToken | None:
    """Load saved legacy Bearer headers."""
    data = _read_json(_legacy_auth_cache_file())
    if not data:
        return None
    token = AuthToken.from_dict(data)
    return token if token.is_legacy else None


def save_legacy_token(token: AuthToken) -> None:
    """Persist legacy Bearer headers used by legacy-only commands."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _legacy_auth_cache_file().write_text(
        json.dumps(token.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load_from_env() -> AuthToken | None:
    api_key = (
        os.environ.get("GETNOTE_API_KEY")
        or os.environ.get("GETNOTES_API_KEY")
        or os.environ.get("BIJI_API_KEY")
    )
    client_id = (
        os.environ.get("GETNOTE_CLIENT_ID")
        or os.environ.get("GETNOTES_CLIENT_ID")
        or os.environ.get("BIJI_CLIENT_ID")
    )
    if api_key and client_id:
        return AuthToken(api_key=api_key, client_id=client_id, extracted_at=time.time())
    return None


def _load_from_official_cli_config() -> AuthToken | None:
    """Best-effort import from the official getnote CLI config."""
    for path in OFFICIAL_CONFIG_CANDIDATES:
        data = _read_json(path)
        if not data:
            continue
        api_key = data.get("api_key") or data.get("apiKey") or data.get("authorization")
        client_id = data.get("client_id") or data.get("clientId")
        if api_key and client_id:
            return AuthToken(api_key=api_key, client_id=client_id, extracted_at=time.time())
    return None


def get_or_refresh_token(force_login: bool = False) -> AuthToken:
    """Get official OpenAPI credentials.

    Raises RuntimeError when API Key / Client ID are not configured. Official
    capabilities never fall back to legacy Bearer tokens.
    """
    if not force_login:
        cached = load_cached_token()
        if cached and cached.is_openapi:
            return cached

        env_token = _load_from_env()
        if env_token:
            return env_token

        official_cli_token = _load_from_official_cli_config()
        if official_cli_token:
            return official_cli_token

    raise RuntimeError(
        "未配置 Get 笔记 OpenAPI 凭证。请运行 `getnotes login --api-key <key> "
        "--client-id <client_id>`，或设置 GETNOTE_API_KEY / GETNOTE_CLIENT_ID。"
    )


def _legacy_auth_cache_file() -> Path:
    if CONFIG_DIR != LEGACY_AUTH_CACHE_FILE.parent:
        return CONFIG_DIR / LEGACY_AUTH_CACHE_FILE.name
    return LEGACY_AUTH_CACHE_FILE


def get_or_refresh_legacy_token(force_login: bool = False) -> AuthToken:
    """Get a legacy Bearer token for legacy-only commands."""
    if not force_login:
        cached = load_cached_legacy_token()
        if cached and not cached.is_expired():
            return cached
        if cached and cached.is_expired():
            logger.warning("⚠️  Legacy token 已过期，需要重新登录...")

    from getnotes_cli.cdp import extract_auth_via_cdp

    headers = extract_auth_via_cdp()
    if not headers or "Authorization" not in headers:
        raise RuntimeError("❌ Legacy 登录失败，未能获取 Authorization token")

    token = AuthToken(
        authorization=headers["Authorization"],
        csrf_token=headers.get("Xi-Csrf-Token", ""),
        extra_headers={
            k: v for k, v in headers.items()
            if k not in ("Authorization", "Xi-Csrf-Token")
        },
        extracted_at=time.time(),
    )
    save_legacy_token(token)
    return token


def login_with_api_key(api_key: str, client_id: str) -> AuthToken:
    """Persist official OpenAPI credentials."""
    token = AuthToken(api_key=api_key.strip(), client_id=client_id.strip(), extracted_at=time.time())
    save_token(token)
    return token


def login_with_token(bearer_token: str) -> AuthToken:
    """Persist a legacy Bearer token for legacy-only commands."""
    if not bearer_token.startswith("Bearer "):
        bearer_token = f"Bearer {bearer_token}"

    token = AuthToken(
        authorization=bearer_token,
        extracted_at=time.time(),
    )
    save_legacy_token(token)
    return token
