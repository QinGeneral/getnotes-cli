"""Official OpenAPI knowledge-base note downloader."""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import httpx

from getnotes_cli.auth import AuthToken
from getnotes_cli.config import REQUEST_DELAY
from getnotes_cli.downloader import _normalize_openapi_note, _with_cache_hash
from getnotes_cli.markdown import get_file_extension, sanitize_filename
from getnotes_cli.notebook import fetch_notebook_notes
from getnotes_cli.openapi_client import OpenAPIClient

logger = logging.getLogger(__name__)


class OpenAPINotebookDownloader:
    """Downloads notes in a knowledge base through the official OpenAPI."""

    def __init__(
        self,
        token: AuthToken,
        output_dir: Path,
        *,
        delay: float = REQUEST_DELAY,
        force: bool = False,
        save_json: bool = False,
    ):
        self.token = token
        self.output_dir = output_dir
        self.delay = delay
        self.force = force
        self.save_json = save_json
        self.file_client = httpx.Client(timeout=60)
        self.stats = {"notes": 0, "files": 0, "skipped": 0}

    def download_notebook(self, notebook: dict) -> dict:
        name = notebook.get("name", "未命名知识库")
        topic_id = str(notebook.get("topic_id") or notebook.get("id_alias") or notebook.get("id"))
        total_count = notebook.get("extend_data", {}).get("all_resource_count", "?")

        notebook_dir = self.output_dir / "notebooks" / sanitize_filename(name)
        notes_dir = notebook_dir / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)

        logger.info("=" * 60)
        logger.info("📚 知识库(OpenAPI): %s", name)
        logger.info("   笔记数: %s | ID: %s", total_count, topic_id)
        logger.info("   输出目录: %s", notebook_dir)
        logger.info("=" * 60)

        stats = {"notes": 0, "files": 0, "skipped": 0}
        page = 1
        with OpenAPIClient(self.token, min_interval=max(1.0, self.delay)) as api_client:
            while True:
                logger.info("📄 正在拉取知识库笔记第 %d 页...", page)
                content = fetch_notebook_notes(
                    self.token,
                    topic_id,
                    page=page,
                    client=api_client,
                )
                notes = content.get("notes", []) or []
                if not notes:
                    break

                for item in notes:
                    note_id = str(item.get("note_id") or item.get("id") or "")
                    detail = api_client.note_detail(note_id) if note_id else item
                    note = _with_cache_hash(_normalize_openapi_note({**item, **detail}))
                    self._process_note(note, notes_dir)
                    stats["notes"] += 1

                if not content.get("has_more"):
                    break
                page += 1
                time.sleep(self.delay)

        self._generate_notebook_index(notebook, notebook_dir, stats)
        for key in stats:
            self.stats[key] += stats[key]
        logger.info("✅ 知识库 [%s] 下载完成: %d 篇笔记", name, stats["notes"])
        return stats

    def download_all(self, notebooks: list[dict]) -> dict:
        logger.info("🚀 开始下载 %d 个知识库...", len(notebooks))
        for i, nb in enumerate(notebooks, 1):
            name = nb.get("name", "未命名")
            logger.info("[%d/%d] 正在处理知识库: %s", i, len(notebooks), name)
            try:
                self.download_notebook(nb)
            except Exception as e:
                logger.error("  ❌ 下载失败: %s", e)
            time.sleep(self.delay)
        self._print_summary(len(notebooks))
        return self.stats

    def _process_note(self, note: dict, notes_dir: Path) -> None:
        title = note.get("title", "").strip() or "无标题"
        note_id = note.get("note_id", note.get("id", "unknown"))
        created_at = note.get("created_at", "")
        folder_name = self._make_note_folder_name(title, created_at, note_id)
        note_dir = notes_dir / folder_name

        if note_dir.exists() and not self.force and (note_dir / "note.md").exists():
            logger.info("    ⏭ 已存在: %s", title[:40])
            return

        note_dir.mkdir(parents=True, exist_ok=True)
        attachments_dir = note_dir / "attachments"
        self._download_attachments(note, attachments_dir)

        from getnotes_cli.markdown import note_to_markdown

        (note_dir / "note.md").write_text(
            note_to_markdown(note, attachments_dir, note_dir),
            encoding="utf-8",
        )
        if self.save_json:
            (note_dir / "note.json").write_text(
                json.dumps(note, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        logger.info("    ✨ %s", title[:60])

    def _download_attachments(self, note: dict, attachments_dir: Path) -> bool:
        has = False
        for i, att in enumerate(note.get("attachments", [])):
            att_url = att.get("url", "") or att.get("play_url", "") or att.get("download_url", "")
            att_type = att.get("type", "")
            if att_url and att_type != "link":
                has = True
                ext = get_file_extension(att_url, f".{att_type or 'bin'}")
                self._download_file(att_url, attachments_dir / f"attachment_{i + 1}{ext}")

        images = note.get("original_images", []) or note.get("small_images", []) or note.get("body_images", [])
        for i, img in enumerate(images):
            img_url = img if isinstance(img, str) else img.get("url", "") if isinstance(img, dict) else ""
            if img_url:
                has = True
                ext = get_file_extension(img_url, ".jpg")
                self._download_file(img_url, attachments_dir / f"image_{i + 1}{ext}")
        return has

    def _download_file(self, url: str, save_path: Path) -> bool:
        try:
            if save_path.exists() and not self.force:
                return True
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with self.file_client.stream("GET", url, timeout=60) as resp:
                resp.raise_for_status()
                with open(save_path, "wb") as f:
                    for chunk in resp.iter_bytes(8192):
                        f.write(chunk)
            kb = save_path.stat().st_size / 1024
            logger.info("      ✅ 下载: %s (%.1f KB)", save_path.name, kb)
            return True
        except Exception as e:
            logger.error("      ❌ 下载失败: %s - %s", save_path.name, e)
            return False

    def _make_note_folder_name(self, title: str, created_at: str, note_id: str) -> str:
        date_prefix = ""
        if created_at:
            try:
                dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
                date_prefix = dt.strftime("%Y%m%d_%H%M%S")
            except ValueError:
                date_prefix = created_at.replace(" ", "_").replace(":", "")
        base = f"{date_prefix}_{title}" if title else f"{date_prefix}_{note_id}"
        return sanitize_filename(base)

    def _generate_notebook_index(self, notebook: dict, notebook_dir: Path, stats: dict) -> None:
        name = notebook.get("name", "未命名知识库")
        index_path = notebook_dir / "INDEX.md"
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(f"# 📚 {name}\n\n")
            f.write(f"- 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- 笔记数: {stats['notes']}\n")
            f.write(f"- 文件数: {stats['files']}\n\n")
            notes_dir = notebook_dir / "notes"
            if notes_dir.exists():
                dirs = sorted(d for d in notes_dir.iterdir() if d.is_dir())
                if dirs:
                    f.write("## 笔记列表\n\n")
                    f.write("| # | 笔记 |\n")
                    f.write("|---|------|\n")
                    for i, d in enumerate(dirs, 1):
                        md_file = d / "note.md"
                        if md_file.exists():
                            f.write(f"| {i} | [{d.name}](notes/{d.name}/note.md) |\n")

    def _print_summary(self, total_notebooks: int) -> None:
        logger.info("=" * 60)
        logger.info("📊 全部知识库下载总结")
        logger.info("=" * 60)
        logger.info("  📚 知识库数:   %d", total_notebooks)
        logger.info("  📝 笔记:       %d 篇", self.stats["notes"])
        logger.info("  📁 文件:       %d 个", self.stats["files"])
        logger.info("  📂 输出目录:   %s", self.output_dir.resolve())
        logger.info("=" * 60)
