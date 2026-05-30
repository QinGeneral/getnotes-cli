"""核心下载逻辑 — 分页拉取笔记并下载附件"""

import json
import logging
import os
import time
import hashlib
from datetime import datetime
from pathlib import Path

import httpx

from getnotes_cli.auth import AuthToken
from getnotes_cli.cache import CacheManager
from getnotes_cli.config import NOTES_API_URL, PAGE_SIZE, REQUEST_DELAY
from getnotes_cli.markdown import (
    get_file_extension,
    note_to_markdown,
    sanitize_filename,
)
from getnotes_cli.openapi_client import OpenAPIClient

logger = logging.getLogger(__name__)


class NoteDownloader:
    """笔记下载器"""

    def __init__(
        self,
        token: AuthToken,
        output_dir: Path,
        *,
        limit: int | None = 100,
        page_size: int = PAGE_SIZE,
        delay: float = REQUEST_DELAY,
        force: bool = False,
        save_json: bool = False,
    ):
        self.token = token
        self.output_dir = output_dir
        self.limit = limit
        self.page_size = page_size
        self.delay = delay
        self.force = force
        self.save_json = save_json

        self.client = httpx.Client(timeout=60)
        self.api_client = OpenAPIClient(token, min_interval=max(1.0, delay))
        self.cache = CacheManager(output_dir)
        self.stats = {"new": 0, "updated": 0, "cached": 0}
        self.total_processed = 0

    def run(self) -> dict:
        """执行下载流程，返回统计结果"""
        # 创建目录结构
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "notes").mkdir(exist_ok=True)
        if self.save_json:
            (self.output_dir / "api_responses").mkdir(exist_ok=True)

        # 加载缓存
        if not self.force:
            self.cache.load()
            # 缓存为空但本地有笔记文件夹时，自动重建缓存
            notes_dir = self.output_dir / "notes"
            if self.cache.count == 0 and notes_dir.exists() and any(notes_dir.iterdir()):
                self.cache.rebuild_from_disk(notes_dir)

        self._print_banner()

        cursor = ""
        page_num = 0
        total_items = None

        try:
            while True:
                page_num += 1
                logger.info("📄 正在拉取第 %d 页 (cursor=%s) ...",
                            page_num, cursor or "(首页)")

                data = self._fetch_page(cursor)

                # 保存 API 响应
                if self.save_json:
                    resp_path = self.output_dir / "api_responses" / f"page_{page_num:04d}.json"
                    resp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

                content = data.get("c", {})
                notes = content.get("list", [])
                has_more = content.get("has_more", False)
                next_cursor = content.get("cursor", "")

                if total_items is None:
                    total_items = content.get("total_items", "未知")
                    logger.info("📊 服务端笔记总数: %s", total_items)

                if not notes:
                    logger.info("⚠️  本页无数据，结束。")
                    break

                logger.info("  本页 %d 条笔记:", len(notes))

                for note in notes:
                    self._process_note(note)
                    self.total_processed += 1

                    # 定期保存缓存
                    if self.total_processed % 50 == 0:
                        self.cache.save()

                    # 检查限制
                    if self.limit is not None and self.total_processed >= self.limit:
                        logger.info("✅ 已达到下载限制 (%d 条)，停止。", self.limit)
                        logger.info("💡 提示: 若要下载所有笔记，请使用 `getnotes download --all`")
                        break

                if self.limit is not None and self.total_processed >= self.limit:
                    break

                if not has_more:
                    logger.info("✅ 所有笔记已下载完毕！")
                    break

                cursor = next_cursor
                if not cursor:
                    logger.info("✅ 未返回下一页 cursor，停止。")
                    break
                time.sleep(self.delay)

        except KeyboardInterrupt:
            logger.info("⚠️  用户中断下载。")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("❌ Token 已过期或无效 (HTTP 401)")
                logger.info("💡 请重新运行 `getnotes login` 登录以获取新 Token")
            else:
                logger.error("❌ HTTP 错误: %s", e)
                logger.info("💡 可能需要重新登录: getnotes login")
        except Exception as e:
            logger.error("❌ 意外错误: %s", e)
            raise
        finally:
            self.cache.save()
            self.api_client.close()

        # 生成索引
        self._generate_index(total_items)
        self._print_summary()

        return self.stats

    def _fetch_page(self, cursor: str = "") -> dict:
        """拉取一页笔记"""
        data = self.api_client.list_notes(cursor)
        notes = [_normalize_openapi_note(note) for note in data.get("notes", [])]
        return {
            "c": {
                "list": notes,
                "has_more": data.get("has_more", False),
                "cursor": data.get("cursor", ""),
                "total_items": data.get("total") or data.get("total_items") or "未知",
            }
        }

    def _process_note(self, note: dict) -> str:
        """处理单条笔记"""
        note = _with_cache_hash(_normalize_openapi_note(note))
        note_id = note.get("note_id", note.get("id", "unknown"))
        title = note.get("title", "").strip()

        # 列表字段足够时先快速跳过；字段不足时继续拉详情后再判断。
        if not self.force and self.cache.is_cached(note) and self._has_cached_markdown(note_id):
            self._print_status(note_id, title, "⏭ 缓存")
            self.stats["cached"] += 1
            return "cached"

        is_update = self.cache.get(note_id) is not None

        detail = self.api_client.note_detail(note_id)
        note = _with_cache_hash(_normalize_openapi_note({**note, **detail}))
        title = note.get("title", "").strip()

        # 详情字段完整后再次判断，避免重复写 Markdown 和下载附件。
        if not self.force and self.cache.is_cached(note) and self._has_cached_markdown(note_id):
            self._print_status(note_id, title, "⏭ 缓存")
            self.stats["cached"] += 1
            return "cached"

        # 生成文件夹名
        folder_name = self._make_folder_name(note)
        if is_update:
            cached = self.cache.get(note_id)
            if cached and "folder_name" in cached:
                folder_name = cached["folder_name"]

        note_dir = self.output_dir / "notes" / folder_name
        if not is_update and note_dir.exists():
            note_dir = self.output_dir / "notes" / f"{folder_name}_{note_id[-6:]}"
            folder_name = f"{folder_name}_{note_id[-6:]}"

        note_dir.mkdir(parents=True, exist_ok=True)
        attachments_dir = note_dir / "attachments"

        # 下载附件
        has_attachments = self._download_attachments(note, attachments_dir)

        # 生成 Markdown
        md_content = note_to_markdown(note, attachments_dir, note_dir)
        (note_dir / "note.md").write_text(md_content, encoding="utf-8")

        # 保存 JSON（save-json 模式）
        if self.save_json:
            (note_dir / "note.json").write_text(
                json.dumps(note, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        # 更新缓存
        self.cache.update(note_id, {
            "version": note.get("version"),
            "updated_at": note.get("updated_at", ""),
            "content_hash": note.get("content_hash", ""),
            "folder_name": folder_name,
            "title": title,
            "created_at": note.get("created_at", ""),
        })

        action = "🔄 更新" if is_update else "✨ 新增"
        extra = " 📎" if has_attachments else ""
        self._print_status(note_id, title, f"{action}{extra}")
        self.stats["updated" if is_update else "new"] += 1
        return "updated" if is_update else "new"

    def _has_cached_markdown(self, note_id: str) -> bool:
        cached = self.cache.get(note_id)
        if not cached:
            return False
        folder_name = cached.get("folder_name", "")
        if not folder_name:
            return False
        return (self.output_dir / "notes" / folder_name / "note.md").exists()

    def _download_attachments(self, note: dict, attachments_dir: Path) -> bool:
        """下载笔记的附件（音频/图片），返回是否有附件"""
        has = False

        # 音频/文件附件
        for i, att in enumerate(note.get("attachments", [])):
            att_url = att.get("url", "") or att.get("play_url", "") or att.get("download_url", "")
            att_type = att.get("type", "")
            if att_url and att_type != "link":
                has = True
                ext = get_file_extension(att_url, f".{att_type or 'bin'}")
                self._download_file(att_url, attachments_dir / f"attachment_{i + 1}{ext}")

        # 图片
        images = note.get("original_images", []) or note.get("small_images", []) or note.get("body_images", [])
        for i, img in enumerate(images):
            img_url = img if isinstance(img, str) else img.get("url", "") if isinstance(img, dict) else ""
            if img_url:
                has = True
                ext = get_file_extension(img_url, ".jpg")
                self._download_file(img_url, attachments_dir / f"image_{i + 1}{ext}")

        return has

    def _download_file(self, url: str, save_path: Path) -> bool:
        """下载文件，已存在则跳过"""
        try:
            if save_path.exists() and not self.force:
                kb = save_path.stat().st_size / 1024
                logger.info("    ⏭  已存在: %s (%.1f KB)", save_path.name, kb)
                return True

            save_path.parent.mkdir(parents=True, exist_ok=True)
            with self.client.stream("GET", url, timeout=60) as resp:
                resp.raise_for_status()
                with open(save_path, "wb") as f:
                    for chunk in resp.iter_bytes(8192):
                        f.write(chunk)

            kb = save_path.stat().st_size / 1024
            logger.info("    ✅ 已下载: %s (%.1f KB)", save_path.name, kb)
            return True
        except Exception as e:
            logger.error("    ❌ 下载失败: %s - %s", save_path.name, e)
            return False

    def _make_folder_name(self, note: dict) -> str:
        """生成笔记文件夹名"""
        note_id = note.get("note_id", note.get("id", "unknown"))
        title = note.get("title", "").strip()
        created_at = note.get("created_at", "")

        date_prefix = ""
        if created_at:
            try:
                dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
                date_prefix = dt.strftime("%Y%m%d_%H%M%S")
            except ValueError:
                date_prefix = created_at.replace(" ", "_").replace(":", "")

        return sanitize_filename(f"{date_prefix}_{title}" if title else f"{date_prefix}_{note_id}")

    def _print_status(self, note_id: str, title: str, action: str) -> None:
        """打印笔记处理状态"""
        parts = [f"#{self.total_processed + 1}", f"ID:{note_id[-8:]}"]
        if title:
            display = title[:40] + "..." if len(title) > 40 else title
            parts.append(display)
        parts.append(action)
        logger.info("  📝 %s", " | ".join(parts))

    def _print_banner(self) -> None:
        """打印启动信息"""
        logger.info("=" * 60)
        logger.info("🗂️  GetNotes CLI — 得到笔记批量下载工具")
        logger.info("=" * 60)
        mode = "全部笔记" if self.limit is None else f"前 {self.limit} 条"
        logger.info("📥 模式: %s", mode)
        logger.info("📂 输出目录: %s", self.output_dir.resolve())
        logger.info("📄 每页: %d 条 | ⏱️ 间隔: %ss", self.page_size, self.delay)
        if self.save_json:
            logger.info("📝 保存模式: 包含原始 JSON 数据")
        if self.force:
            logger.info("⚡ 强制模式: 忽略所有缓存")
        elif self.cache.count > 0:
            logger.info("💾 缓存: 已有 %d 条笔记记录", self.cache.count)
        logger.info("=" * 60)

    def _print_summary(self) -> None:
        """打印下载总结"""
        logger.info("=" * 60)
        logger.info("📊 下载总结")
        logger.info("=" * 60)
        logger.info("  📋 处理笔记:   %d 条", self.total_processed)
        logger.info("  ✨ 新增:       %d 条", self.stats['new'])
        logger.info("  🔄 更新:       %d 条", self.stats['updated'])
        logger.info("  ⏭  缓存跳过:   %d 条", self.stats['cached'])
        logger.info("  💾 缓存记录:   %d 条", self.cache.count)
        logger.info("  📁 输出目录:   %s", self.output_dir.resolve())
        logger.info("=" * 60)

    def _generate_index(self, total_items) -> None:
        """生成索引文件（优先使用缓存清单，无需依赖 note.json）"""
        index_path = self.output_dir / "INDEX.md"

        # 建立 folder_name → (note_id, title, created_at) 的映射（来自缓存）
        cache_by_folder: dict[str, dict] = {}
        for nid, info in self.cache.manifest.items():
            fn = info.get("folder_name", "")
            if fn:
                cache_by_folder[fn] = {
                    "note_id": nid,
                    "title": info.get("title", "(无标题)"),
                    "created_at": info.get("created_at", ""),
                }

        with open(index_path, "w", encoding="utf-8") as f:
            f.write("# Get笔记 导出索引\n\n")
            f.write(f"- 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- 处理笔记数: {self.total_processed}\n")
            f.write(f"- 服务端总数: {total_items}\n")
            f.write(f"- 新增: {self.stats['new']} | 更新: {self.stats['updated']} | 缓存跳过: {self.stats['cached']}\n\n")
            f.write("## 笔记列表\n\n")
            f.write("| # | 标题 | 创建时间 | 文件夹 |\n")
            f.write("|---|------|----------|--------|\n")

            notes_dir = self.output_dir / "notes"
            if notes_dir.exists():
                folders = sorted(
                    (d for d in notes_dir.iterdir() if d.is_dir()),
                    reverse=True,  # 时间降序
                )
                for i, folder in enumerate(folders, 1):
                    md_file = folder / "note.md"
                    if not md_file.exists():
                        continue
                    cache_info = cache_by_folder.get(folder.name)
                    if cache_info:
                        nid = cache_info["note_id"]
                        title = cache_info["title"] or "(无标题)"
                        created = cache_info["created_at"][:10] if cache_info["created_at"] else ""
                    else:
                        # 回退：尝试读 note.json
                        json_file = folder / "note.json"
                        if json_file.exists():
                            try:
                                nd = json.loads(json_file.read_text(encoding="utf-8"))
                                nid = nd.get("note_id", "")
                                title = nd.get("title", "(无标题)")
                                created = nd.get("created_at", "")[:10]
                            except Exception:
                                nid, title, created = "", folder.name, ""
                        else:
                            nid, title, created = "", folder.name, ""
                    f.write(f"| {i} | [{title}](notes/{folder.name}/note.md) | {created} | `{folder.name}` |\n")


def _normalize_openapi_note(note: dict) -> dict:
    """Normalize official OpenAPI note fields to the local Markdown shape."""
    normalized = dict(note)
    note_id = str(note.get("note_id") or note.get("id") or "")
    if note_id:
        normalized["note_id"] = note_id
        normalized["id"] = note_id

    normalized["created_at"] = _normalize_time_value(
        note.get("created_at") or note.get("create_time") or note.get("created_time")
    )
    normalized["updated_at"] = _normalize_time_value(
        note.get("updated_at") or note.get("update_time") or note.get("edit_time")
    )
    if "version" not in normalized and "timeline_version" in note:
        normalized["version"] = note.get("timeline_version")

    tags = []
    for tag in note.get("tags", []) or []:
        if isinstance(tag, str):
            tags.append({"name": tag})
        elif isinstance(tag, dict):
            tags.append(tag)
    normalized["tags"] = tags

    topics = []
    for topic in note.get("topics", []) or []:
        if isinstance(topic, str):
            topics.append({"topic_name": topic})
        elif isinstance(topic, dict):
            topic_name = topic.get("topic_name") or topic.get("name")
            topics.append({**topic, "topic_name": topic_name or ""})
    normalized["topics"] = topics

    images = list(note.get("original_images") or note.get("image_urls") or [])
    attachments = []
    for att in note.get("attachments", []) or []:
        if not isinstance(att, dict):
            continue
        att_type = (att.get("type") or att.get("attachment_type") or "").lower()
        att_url = (
            att.get("url")
            or att.get("play_url")
            or att.get("download_url")
            or att.get("access_url")
            or ""
        )
        if att_type == "image" and att_url:
            images.append(att_url)
            continue
        normalized_att = dict(att)
        normalized_att["type"] = att_type or "file"
        normalized_att["url"] = att_url
        duration = normalized_att.get("duration")
        if isinstance(duration, (int, float)) and 0 < duration < 24 * 60 * 60:
            normalized_att["duration"] = int(duration * 1000)
        attachments.append(normalized_att)

    audio = note.get("audio") or {}
    if isinstance(audio, dict):
        audio_url = audio.get("play_url") or audio.get("url")
        if audio_url:
            duration = audio.get("duration", 0)
            if isinstance(duration, (int, float)) and 0 < duration < 24 * 60 * 60:
                duration = int(duration * 1000)
            attachments.append({
                "type": "audio",
                "url": audio_url,
                "title": audio.get("title", "audio"),
                "duration": duration,
            })
        if audio.get("original") and not normalized.get("ref_content"):
            normalized["ref_content"] = audio["original"]

    web_page = note.get("web_page") or {}
    if isinstance(web_page, dict):
        if web_page.get("content") and not normalized.get("ref_content"):
            normalized["ref_content"] = web_page["content"]
        if web_page.get("url"):
            normalized["res_info"] = {
                "title": web_page.get("title") or normalized.get("title", ""),
                "url": web_page["url"],
            }

    normalized["attachments"] = attachments
    normalized["original_images"] = images
    return normalized


def _with_cache_hash(note: dict) -> dict:
    """Attach a stable hash over fields that affect local Markdown output."""
    normalized = dict(note)
    fingerprint = {
        "title": normalized.get("title", ""),
        "content": normalized.get("content", ""),
        "ref_content": normalized.get("ref_content", ""),
        "attachments": normalized.get("attachments", []),
        "original_images": normalized.get("original_images", []),
        "small_images": normalized.get("small_images", []),
        "body_images": normalized.get("body_images", []),
        "res_info": normalized.get("res_info", {}),
        "topics": normalized.get("topics", []),
        "tags": normalized.get("tags", []),
        "note_type": normalized.get("note_type", ""),
        "entry_type": normalized.get("entry_type", ""),
    }
    payload = json.dumps(fingerprint, ensure_ascii=False, sort_keys=True, default=str)
    normalized["content_hash"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return normalized


def _normalize_time_value(value) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)):
        if value > 10_000_000_000:
            value = value / 1000
        try:
            return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")
        except (OSError, OverflowError, ValueError):
            return str(value)
    return str(value)
