"""Tests for getnotes_cli.auth module"""

import json
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from getnotes_cli.auth import AuthToken, load_cached_token, save_token, login_with_token
from getnotes_cli.config import DEFAULT_HEADERS


class TestAuthToken:
    def _make_token(self, **kwargs):
        defaults = {
            "authorization": "Bearer test-token",
            "csrf_token": "csrf-123",
            "extra_headers": {},
            "extracted_at": time.time(),
        }
        defaults.update(kwargs)
        return AuthToken(**defaults)

    def test_to_dict_roundtrip(self):
        token = self._make_token()
        d = token.to_dict()
        restored = AuthToken.from_dict(d)
        assert restored.authorization == token.authorization
        assert restored.csrf_token == token.csrf_token
        assert restored.extra_headers == token.extra_headers
        assert restored.extracted_at == token.extracted_at

    def test_from_dict_missing_optional_fields(self):
        d = {"authorization": "Bearer x"}
        token = AuthToken.from_dict(d)
        assert token.csrf_token == ""
        assert token.extra_headers == {}
        assert token.extracted_at == 0

    def test_is_expired_fresh_token(self):
        token = self._make_token(extracted_at=time.time())
        assert not token.is_expired()

    def test_is_expired_old_token(self):
        # 26 minutes ago
        token = self._make_token(extracted_at=time.time() - 26 * 60)
        assert token.is_expired()

    def test_is_expired_custom_max_age(self):
        token = self._make_token(extracted_at=time.time() - 10 * 60)
        assert token.is_expired(max_age_minutes=5)
        assert not token.is_expired(max_age_minutes=15)

    def test_get_headers_includes_authorization(self):
        token = self._make_token(authorization="Bearer abc")
        headers = token.get_headers()
        assert headers["Authorization"] == "Bearer abc"

    def test_get_headers_includes_csrf_token(self):
        token = self._make_token(csrf_token="csrf-xyz")
        headers = token.get_headers()
        assert headers["Xi-Csrf-Token"] == "csrf-xyz"

    def test_get_headers_no_csrf_when_empty(self):
        token = self._make_token(csrf_token="")
        headers = token.get_headers()
        assert "Xi-Csrf-Token" not in headers

    def test_get_headers_includes_extra_headers(self):
        token = self._make_token(extra_headers={"X-Custom": "value"})
        headers = token.get_headers()
        assert headers["X-Custom"] == "value"

    def test_get_headers_includes_default_headers(self):
        token = self._make_token()
        headers = token.get_headers()
        for key in DEFAULT_HEADERS:
            assert key in headers

    def test_to_dict_contains_all_fields(self):
        token = self._make_token(
            authorization="Bearer t",
            csrf_token="c",
            extra_headers={"X-A": "B"},
            extracted_at=1234.0,
        )
        d = token.to_dict()
        assert d["authorization"] == "Bearer t"
        assert d["csrf_token"] == "c"
        assert d["extra_headers"] == {"X-A": "B"}
        assert d["extracted_at"] == 1234.0


class TestLoadCachedToken:
    def test_returns_none_when_file_missing(self, tmp_path):
        with patch("getnotes_cli.auth.AUTH_CACHE_FILE", tmp_path / "nonexistent.json"):
            assert load_cached_token() is None

    def test_returns_token_when_file_valid(self, tmp_path):
        cache_file = tmp_path / "auth.json"
        data = {
            "authorization": "Bearer cached",
            "csrf_token": "",
            "extra_headers": {},
            "extracted_at": time.time(),
        }
        cache_file.write_text(json.dumps(data), encoding="utf-8")
        with patch("getnotes_cli.auth.AUTH_CACHE_FILE", cache_file):
            token = load_cached_token()
        assert token is not None
        assert token.authorization == "Bearer cached"

    def test_returns_none_on_invalid_json(self, tmp_path):
        cache_file = tmp_path / "auth.json"
        cache_file.write_text("not-json", encoding="utf-8")
        with patch("getnotes_cli.auth.AUTH_CACHE_FILE", cache_file):
            assert load_cached_token() is None

    def test_returns_none_on_missing_key(self, tmp_path):
        cache_file = tmp_path / "auth.json"
        cache_file.write_text(json.dumps({"no_auth_key": "x"}), encoding="utf-8")
        with patch("getnotes_cli.auth.AUTH_CACHE_FILE", cache_file):
            assert load_cached_token() is None


class TestSaveToken:
    def test_saves_token_to_file(self, tmp_path):
        cache_file = tmp_path / "auth.json"
        token = AuthToken(
            authorization="Bearer saved",
            csrf_token="c",
            extra_headers={},
            extracted_at=123.0,
        )
        with (
            patch("getnotes_cli.auth.AUTH_CACHE_FILE", cache_file),
            patch("getnotes_cli.auth.CONFIG_DIR", tmp_path),
        ):
            save_token(token)
        assert cache_file.exists()
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        assert data["authorization"] == "Bearer saved"

    def test_creates_config_dir_if_missing(self, tmp_path):
        sub_dir = tmp_path / "subdir"
        cache_file = sub_dir / "auth.json"
        token = AuthToken(authorization="Bearer x", extracted_at=0.0)
        with (
            patch("getnotes_cli.auth.AUTH_CACHE_FILE", cache_file),
            patch("getnotes_cli.auth.CONFIG_DIR", sub_dir),
        ):
            save_token(token)
        assert cache_file.exists()


class TestLoginWithToken:
    def test_adds_bearer_prefix_if_missing(self, tmp_path):
        cache_file = tmp_path / "auth.json"
        with (
            patch("getnotes_cli.auth.AUTH_CACHE_FILE", cache_file),
            patch("getnotes_cli.auth.CONFIG_DIR", tmp_path),
        ):
            token = login_with_token("raw-token-value")
        assert token.authorization == "Bearer raw-token-value"

    def test_keeps_bearer_prefix_if_present(self, tmp_path):
        cache_file = tmp_path / "auth.json"
        with (
            patch("getnotes_cli.auth.AUTH_CACHE_FILE", cache_file),
            patch("getnotes_cli.auth.CONFIG_DIR", tmp_path),
        ):
            token = login_with_token("Bearer already-prefixed")
        assert token.authorization == "Bearer already-prefixed"

    def test_saves_token_to_cache(self, tmp_path):
        cache_file = tmp_path / "auth.json"
        with (
            patch("getnotes_cli.auth.AUTH_CACHE_FILE", cache_file),
            patch("getnotes_cli.auth.CONFIG_DIR", tmp_path),
        ):
            login_with_token("my-token")
        assert cache_file.exists()

    def test_extracted_at_is_recent(self, tmp_path):
        cache_file = tmp_path / "auth.json"
        before = time.time()
        with (
            patch("getnotes_cli.auth.AUTH_CACHE_FILE", cache_file),
            patch("getnotes_cli.auth.CONFIG_DIR", tmp_path),
        ):
            token = login_with_token("t")
        assert token.extracted_at >= before
