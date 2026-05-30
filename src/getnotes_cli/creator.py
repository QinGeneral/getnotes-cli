"""Note creation through the official Get 笔记 OpenAPI."""

from pathlib import Path
from typing import Any

from getnotes_cli.auth import AuthToken
from getnotes_cli.openapi_client import OpenAPIClient


class NoteCreator:
    """Creates text, link, and image notes via the official OpenAPI."""

    def __init__(self, token: AuthToken):
        self.token = token

    def create_note(
        self,
        text: str,
        image_paths: list[Path] | None = None,
        *,
        title: str = "",
        tags: list[str] | None = None,
        topic_id: str | None = None,
        wait: bool = True,
    ) -> dict[str, Any]:
        """Create a text note, or an image-text note when images are provided."""
        image_paths = image_paths or []
        with OpenAPIClient(self.token) as client:
            if not image_paths:
                return client.save_text_note(
                    text,
                    title=title,
                    tags=tags,
                    topic_id=topic_id,
                )

            image_urls = client.upload_images(image_paths)
            data = client.save_image_note(
                image_urls,
                content=text,
                title=title,
                tags=tags,
                topic_id=topic_id,
            )
            return _resolve_async_result(client, data, wait=wait)

    def create_note_from_link(
        self,
        url: str,
        *,
        title: str = "",
        tags: list[str] | None = None,
        topic_id: str | None = None,
        wait: bool = True,
    ) -> dict[str, Any]:
        """Create a link note and optionally wait for asynchronous processing."""
        with OpenAPIClient(self.token) as client:
            data = client.save_link_note(
                url,
                title=title,
                tags=tags,
                topic_id=topic_id,
            )
            return _resolve_async_result(client, data, wait=wait)


def _resolve_async_result(
    client: OpenAPIClient,
    data: dict[str, Any],
    *,
    wait: bool,
) -> dict[str, Any]:
    """Return direct note data or poll the first async task until completion."""
    if data.get("note_id") or not data.get("tasks"):
        return data

    task = data["tasks"][0]
    task_id = task.get("task_id")
    if not task_id or not wait:
        return data

    task_result = client.wait_for_task(task_id)
    merged = dict(data)
    merged.update(task_result)
    return merged
