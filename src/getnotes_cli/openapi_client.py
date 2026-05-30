"""Official Get 笔记 OpenAPI client."""

import logging
import time
from pathlib import Path
from typing import Any

import httpx
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder

from getnotes_cli.auth import AuthToken
from getnotes_cli.config import (
    OPENAPI_IMAGE_UPLOAD_TOKEN_URL,
    OPENAPI_KNOWLEDGE_CREATE_URL,
    OPENAPI_KNOWLEDGE_LIST_URL,
    OPENAPI_KNOWLEDGE_NOTE_ADD_URL,
    OPENAPI_KNOWLEDGE_NOTE_REMOVE_URL,
    OPENAPI_KNOWLEDGE_NOTES_URL,
    OPENAPI_KNOWLEDGE_RECALL_URL,
    OPENAPI_KNOWLEDGE_SUBSCRIBE_LIST_URL,
    OPENAPI_NOTE_DELETE_URL,
    OPENAPI_NOTE_DETAIL_URL,
    OPENAPI_NOTE_LIST_URL,
    OPENAPI_NOTE_SAVE_URL,
    OPENAPI_NOTE_SHARING_URL,
    OPENAPI_NOTE_TASK_PROGRESS_URL,
    OPENAPI_NOTE_UPDATE_URL,
    OPENAPI_RECALL_URL,
    OPENAPI_TAGS_ADD_URL,
    OPENAPI_TAGS_DELETE_URL,
)


logger = logging.getLogger(__name__)


class OpenAPIError(RuntimeError):
    """Raised when the official OpenAPI returns an error response."""


class OpenAPIClient:
    """Small typed-ish wrapper around the official OpenAPI."""

    def __init__(
        self,
        auth: AuthToken,
        *,
        timeout: float = 60,
        min_interval: float = 1.0,
        max_retries: int = 6,
    ):
        if not auth.is_openapi:
            raise ValueError("OpenAPIClient requires API Key and Client ID credentials")
        self.auth = auth
        self.client = httpx.Client(timeout=timeout)
        self.min_interval = max(0.0, min_interval)
        self.max_retries = max_retries
        self._last_request_at = 0.0

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "OpenAPIClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @property
    def headers(self) -> dict[str, str]:
        return self.auth.get_headers()

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        last_resp: httpx.Response | None = None
        last_data: dict[str, Any] | None = None

        for attempt in range(self.max_retries + 1):
            self._throttle()
            resp = self.client.request(
                method,
                url,
                headers=self.headers,
                params=params,
                json=json,
            )
            last_resp = resp
            last_data = self._safe_json(resp)

            if self._is_rate_limited(resp, last_data):
                if attempt >= self.max_retries:
                    break
                delay = self._retry_delay(resp, attempt)
                logger.warning(
                    "OpenAPI 请求频率超限，%.1fs 后重试 (%d/%d)",
                    delay,
                    attempt + 1,
                    self.max_retries,
                )
                time.sleep(delay)
                continue

            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                detail = self._response_detail(e.response, last_data)
                raise OpenAPIError(f"OpenAPI HTTP {e.response.status_code}{detail}") from e

            data = last_data if last_data is not None else resp.json()
            if data.get("success") is False:
                error = data.get("error") or data.get("message") or data
                raise OpenAPIError(f"OpenAPI 请求失败: {error}")
            code = data.get("code")
            if code not in (None, 0):
                raise OpenAPIError(f"OpenAPI 请求失败: {data}")
            return data.get("data", data)

        if last_resp is not None:
            detail = self._response_detail(last_resp, last_data)
            raise OpenAPIError(f"OpenAPI HTTP {last_resp.status_code}{detail}")
        raise OpenAPIError("OpenAPI 请求失败：没有收到响应")

    def _throttle(self) -> None:
        if self.min_interval <= 0:
            return
        now = time.monotonic()
        elapsed = now - self._last_request_at
        wait = self.min_interval - elapsed
        if self._last_request_at and wait > 0:
            time.sleep(wait)
        self._last_request_at = time.monotonic()

    def _safe_json(self, resp: httpx.Response) -> dict[str, Any] | None:
        try:
            data = resp.json()
        except Exception:
            return None
        return data if isinstance(data, dict) else None

    def _is_rate_limited(self, resp: httpx.Response, data: dict[str, Any] | None) -> bool:
        if resp.status_code == 429:
            return True
        if not data:
            return False
        error = data.get("error")
        if not isinstance(error, dict):
            return False
        return error.get("reason") == "qps_bucket_exceeded" or error.get("code") == 10202

    def _retry_delay(self, resp: httpx.Response, attempt: int) -> float:
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), 30.0)
            except ValueError:
                pass
        return min(1.5 * (2 ** attempt), 30.0)

    def _response_detail(
        self,
        resp: httpx.Response,
        data: dict[str, Any] | None,
    ) -> str:
        if data is not None:
            return f": {data}"
        return f": {resp.text[:300]}"

    # ------------------------------------------------------------------
    # Notes
    # ------------------------------------------------------------------

    def save_text_note(
        self,
        content: str,
        *,
        title: str = "",
        tags: list[str] | None = None,
        topic_id: str | None = None,
        parent_id: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "note_type": "plain_text",
            "title": title,
            "content": content,
            "tags": tags or [],
        }
        if topic_id:
            payload["topic_id"] = topic_id
        if parent_id is not None:
            payload["parent_id"] = parent_id
        return self._request("POST", OPENAPI_NOTE_SAVE_URL, json=payload)

    def save_link_note(
        self,
        url: str,
        *,
        title: str = "",
        tags: list[str] | None = None,
        topic_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "note_type": "link",
            "title": title,
            "link_url": url,
            "tags": tags or [],
        }
        if topic_id:
            payload["topic_id"] = topic_id
        return self._request("POST", OPENAPI_NOTE_SAVE_URL, json=payload)

    def save_image_note(
        self,
        image_urls: list[str],
        *,
        content: str = "",
        title: str = "",
        tags: list[str] | None = None,
        topic_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "note_type": "img_text",
            "title": title,
            "content": content,
            "image_urls": image_urls,
            "tags": tags or [],
        }
        if topic_id:
            payload["topic_id"] = topic_id
        return self._request("POST", OPENAPI_NOTE_SAVE_URL, json=payload)

    def task_progress(self, task_id: str) -> dict[str, Any]:
        return self._request("POST", OPENAPI_NOTE_TASK_PROGRESS_URL, json={"task_id": task_id})

    def wait_for_task(
        self,
        task_id: str,
        *,
        poll_interval: float = 10.0,
        timeout: float = 300.0,
    ) -> dict[str, Any]:
        deadline = time.time() + timeout
        last: dict[str, Any] = {}
        while time.time() < deadline:
            last = self.task_progress(task_id)
            status = last.get("status")
            if status in ("success", "failed"):
                return last
            time.sleep(poll_interval)
        raise OpenAPIError(f"任务 {task_id} 在 {timeout:.0f}s 内未完成，最后状态: {last}")

    def list_notes(self, cursor: str | int | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if cursor not in (None, "", 0, "0"):
            params["cursor"] = cursor
        return self._request("GET", OPENAPI_NOTE_LIST_URL, params=params)

    def note_detail(self, note_id: str, *, image_quality: str = "original") -> dict[str, Any]:
        data = self._request(
            "GET",
            OPENAPI_NOTE_DETAIL_URL,
            params={"id": note_id, "image_quality": image_quality},
        )
        return data.get("note", data)

    def update_note(
        self,
        note_id: str,
        *,
        title: str | None = None,
        content: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"note_id": note_id}
        if title is not None:
            payload["title"] = title
        if content is not None:
            payload["content"] = content
        if tags is not None:
            payload["tags"] = tags
        return self._request("POST", OPENAPI_NOTE_UPDATE_URL, json=payload)

    def delete_note(self, note_id: str) -> dict[str, Any]:
        return self._request("POST", OPENAPI_NOTE_DELETE_URL, json={"note_id": note_id})

    def share_note(self, note_id: str, *, share_exclude_audio: bool = True) -> dict[str, Any]:
        return self._request(
            "POST",
            OPENAPI_NOTE_SHARING_URL,
            json={"note_id": note_id, "share_exclude_audio": share_exclude_audio},
        )

    # ------------------------------------------------------------------
    # Images
    # ------------------------------------------------------------------

    def get_image_upload_tokens(self, mime_type: str, *, count: int = 1) -> list[dict[str, Any]]:
        data = self._request(
            "GET",
            OPENAPI_IMAGE_UPLOAD_TOKEN_URL,
            params={"mime_type": mime_type, "count": count},
        )
        tokens = data.get("tokens") or data.get("list") or data.get("items") or data
        if isinstance(tokens, dict):
            tokens = [tokens]
        if not isinstance(tokens, list):
            raise OpenAPIError(f"图片上传凭证响应格式无法识别: {data}")
        return tokens

    def upload_image(self, image_path: Path, token_info: dict[str, Any]) -> str:
        host = token_info["host"]
        object_key = token_info.get("object_key") or token_info.get("key")
        access_id = token_info.get("accessid") or token_info.get("OSSAccessKeyId")
        signature = token_info.get("signature") or token_info.get("Signature")
        access_url = token_info.get("access_url") or token_info.get("url")
        if not object_key or not access_id or not signature or not access_url:
            raise OpenAPIError(f"图片上传凭证缺少必要字段: {token_info}")

        mime_type = _image_mime_type(image_path.suffix)
        fields: list[tuple[str, Any]] = [
            ("key", object_key),
            ("OSSAccessKeyId", access_id),
            ("policy", token_info["policy"]),
            ("signature", signature),
            ("callback", token_info["callback"]),
            ("Content-Type", mime_type),
        ]
        with image_path.open("rb") as file_obj:
            fields.append(("file", (image_path.name, file_obj, mime_type)))
            encoder = MultipartEncoder(fields=fields)
            resp = requests.post(
                host,
                headers={"Content-Type": encoder.content_type},
                data=encoder,
                timeout=60,
            )
            resp.raise_for_status()
        return access_url

    def upload_images(self, image_paths: list[Path]) -> list[str]:
        if not image_paths:
            return []
        urls: list[str] = []
        grouped: dict[str, list[Path]] = {}
        for path in image_paths:
            ext = path.suffix.lower().lstrip(".")
            if ext == "jpeg":
                ext = "jpg"
            if ext not in ("jpg", "png", "gif", "webp"):
                raise ValueError(f"不支持的图片格式: {path.suffix}")
            grouped.setdefault(ext, []).append(path)

        for ext, paths in grouped.items():
            for start in range(0, len(paths), 9):
                batch = paths[start:start + 9]
                tokens = self.get_image_upload_tokens(ext, count=len(batch))
                if len(tokens) < len(batch):
                    raise OpenAPIError("图片上传凭证数量少于待上传图片数量")
                for path, token_info in zip(batch, tokens):
                    urls.append(self.upload_image(path, token_info))
        return urls

    # ------------------------------------------------------------------
    # Tags / search / knowledge
    # ------------------------------------------------------------------

    def add_tags(self, note_id: str, tags: list[str]) -> dict[str, Any]:
        return self._request("POST", OPENAPI_TAGS_ADD_URL, json={"note_id": note_id, "tags": tags})

    def delete_tag(self, note_id: str, tag_id: str) -> dict[str, Any]:
        return self._request("POST", OPENAPI_TAGS_DELETE_URL, json={"note_id": note_id, "tag_id": tag_id})

    def recall(self, query: str, *, top_k: int = 5) -> list[dict[str, Any]]:
        top_k = max(1, min(top_k, 10))
        data = self._request("POST", OPENAPI_RECALL_URL, json={"query": query, "top_k": top_k})
        return data.get("results", [])

    def recall_knowledge(self, topic_id: str, query: str, *, top_k: int = 5) -> list[dict[str, Any]]:
        top_k = max(1, min(top_k, 10))
        data = self._request(
            "POST",
            OPENAPI_KNOWLEDGE_RECALL_URL,
            json={"topic_id": topic_id, "query": query, "top_k": top_k},
        )
        return data.get("results", [])

    def list_knowledge(self, *, page: int = 1) -> dict[str, Any]:
        return self._request("GET", OPENAPI_KNOWLEDGE_LIST_URL, params={"page": page})

    def list_subscribed_knowledge(self, *, page: int = 1) -> dict[str, Any]:
        return self._request("GET", OPENAPI_KNOWLEDGE_SUBSCRIBE_LIST_URL, params={"page": page})

    def create_knowledge(self, name: str, description: str = "") -> dict[str, Any]:
        return self._request(
            "POST",
            OPENAPI_KNOWLEDGE_CREATE_URL,
            json={"name": name, "description": description},
        )

    def knowledge_notes(self, topic_id: str, *, page: int = 1) -> dict[str, Any]:
        return self._request(
            "GET",
            OPENAPI_KNOWLEDGE_NOTES_URL,
            params={"topic_id": topic_id, "page": page},
        )

    def add_notes_to_knowledge(self, topic_id: str, note_ids: list[str]) -> dict[str, Any]:
        return self._request(
            "POST",
            OPENAPI_KNOWLEDGE_NOTE_ADD_URL,
            json={"topic_id": topic_id, "note_ids": note_ids},
        )

    def remove_notes_from_knowledge(self, topic_id: str, note_ids: list[str]) -> dict[str, Any]:
        return self._request(
            "POST",
            OPENAPI_KNOWLEDGE_NOTE_REMOVE_URL,
            json={"topic_id": topic_id, "note_ids": note_ids},
        )


def _image_mime_type(ext: str) -> str:
    ext = ext.lower().lstrip(".")
    if ext == "jpg":
        ext = "jpeg"
    if ext == "svg":
        return "image/svg+xml"
    return f"image/{ext or 'jpeg'}"
