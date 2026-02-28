"""核心下载逻辑 — 分页拉取笔记并下载附件"""

import json
import logging
import os
import time
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

        since_id = ""
        page_num = 0
        total_items = None

        try:
            while True:
                page_num += 1
                logger.info("📄 正在拉取第 %d 页 (since_id=%s) ...",
                            page_num, since_id or "(首页)")

                data = self._fetch_page(since_id)

                # 保存 API 响应
                if self.save_json:
                    resp_path = self.output_dir / "api_responses" / f"page_{page_num:04d}.json"
                    resp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

                content = data.get("c", {})
                notes = content.get("list", [])
                has_more = content.get("has_more", False)

                if total_items is None:
                    total_items = content.get("total_items", "?")
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

                since_id = notes[-1].get("id", "")
                time.sleep(self.delay)

        except KeyboardInterrupt:
            logger.info("⚠️  用户中断下载。")
        except httpx.HTTPStatusError as e:
            logger.error("❌ HTTP 错误: %s", e)
            logger.info("💡 可能需要重新登录: getnotes login")
        except Exception as e:
            logger.error("❌ 意外错误: %s", e)
            raise
        finally:
            self.cache.save()

        # 生成索引
        self._generate_index(total_items)
        self._print_summary()

        return self.stats

    def _fetch_page(self, since_id: str = "") -> dict:
        """拉取一页笔记"""
        params = {
            "limit": self.page_size,
            "since_id": since_id,
            "sort": "create_desc",
        }
        headers = self.token.get_headers()
        resp = self.client.get(NOTES_API_URL, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _process_note(self, note: dict) -> str:
        """处理单条笔记"""
        note_id = note.get("note_id", note.get("id", "unknown"))
        title = note.get("title", "").strip()

        # 缓存检查
        if not self.force and self.cache.is_cached(note):
            self._print_status(note_id, title, "⏭ 缓存")
            self.stats["cached"] += 1
            return "cached"

        is_update = self.cache.get(note_id) is not None

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
            "folder_name": folder_name,
            "title": title,
            "created_at": note.get("created_at", ""),
        })

        action = "🔄 更新" if is_update else "✨ 新增"
        extra = " 📎" if has_attachments else ""
        self._print_status(note_id, title, f"{action}{extra}")
        self.stats["updated" if is_update else "new"] += 1
        return "updated" if is_update else "new"

    def _download_attachments(self, note: dict, attachments_dir: Path) -> bool:
        """下载笔记的附件（音频/图片），返回是否有附件"""
        has = False

        # 音频附件
        for i, att in enumerate(note.get("attachments", [])):
            att_url = att.get("url", "")
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
        """生成索引文件"""
        index_path = self.output_dir / "INDEX.md"
        with open(index_path, "w", encoding="utf-8") as f:
            f.write("# Get笔记 导出索引\n\n")
            f.write(f"- 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- 处理笔记数: {self.total_processed}\n")
            f.write(f"- 服务端总数: {total_items}\n")
            f.write(f"- 新增: {self.stats['new']} | 更新: {self.stats['updated']} | 缓存跳过: {self.stats['cached']}\n\n")
            f.write("## 笔记列表\n\n")
            f.write("| # | 笔记 ID | 文件夹 |\n")
            f.write("|---|---------|--------|\n")

            notes_dir = self.output_dir / "notes"
            if notes_dir.exists():
                for i, folder in enumerate(sorted(notes_dir.iterdir())):
                    if folder.is_dir():
                        json_file = folder / "note.json"
                        md_file = folder / "note.md"
                        if json_file.exists():
                            try:
                                nd = json.loads(json_file.read_text(encoding="utf-8"))
                                nid = nd.get("note_id", "")
                                title = nd.get("title", "(无标题)")
                                f.write(f"| {i + 1} | `{nid}` | [{title}](notes/{folder.name}/note.md) |\n")
                            except Exception:
                                f.write(f"| {i + 1} | - | [{folder.name}](notes/{folder.name}/note.md) |\n")
                        elif md_file.exists():
                            f.write(f"| {i + 1} | - | [{folder.name}](notes/{folder.name}/note.md) |\n")
