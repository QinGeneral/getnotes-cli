"""知识库笔记下载器 — 下载知识库内的笔记资源并保存为 Markdown"""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import httpx

from getnotes_cli.auth import AuthToken
from getnotes_cli.config import REQUEST_DELAY
from getnotes_cli.markdown import (
    get_file_extension,
    sanitize_filename,
)
from getnotes_cli.notebook import fetch_notebook_resources

logger = logging.getLogger(__name__)


class NotebookDownloader:
    """知识库笔记下载器"""

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

        self.client = httpx.Client(timeout=60)
        self.stats = {"notes": 0, "files": 0, "skipped": 0}
        # note_id → existing folder Path mapping (populated by _scan_existing_notes)
        self._existing_notes: dict[str, Path] = {}

    def download_notebook(self, notebook: dict) -> dict:
        """下载单个知识库的所有笔记。

        Args:
            notebook: 知识库信息（来自 fetch_notebooks）

        Returns:
            统计结果
        """
        name = notebook.get("name", "未命名知识库")
        topic_id_alias = notebook.get("id_alias", "")
        root_dir = notebook.get("root_dir", {})
        directory_id = root_dir.get("id", 0)
        total_count = notebook.get("extend_data", {}).get("all_resource_count", "?")

        # 创建知识库目录
        notebook_dir = self.output_dir / "notebooks" / sanitize_filename(name)
        notebook_dir.mkdir(parents=True, exist_ok=True)

        # 扫描已有笔记文件夹，建立 note_id → folder 映射
        self._existing_notes = {}
        self._scan_existing_notes(notebook_dir)

        logger.info("=" * 60)
        logger.info("📚 知识库: %s", name)
        logger.info("   内容总数: %s | ID: %s", total_count, topic_id_alias)
        logger.info("   输出目录: %s", notebook_dir)
        logger.info("=" * 60)

        local_stats = {"notes": 0, "files": 0, "skipped": 0}

        # 递归下载根目录及其所有子目录
        self._download_directory(
            topic_id_alias, directory_id, notebook_dir, local_stats
        )

        # 生成知识库索引
        self._generate_notebook_index(notebook, notebook_dir, local_stats)

        # 汇总统计
        for k in local_stats:
            self.stats[k] += local_stats[k]

        logger.info("✅ 知识库 [%s] 下载完成: %d 篇笔记, %d 个文件",
                     name, local_stats['notes'], local_stats['files'])

        return local_stats

    def _download_directory(
        self,
        topic_id_alias: str,
        directory_id: int,
        target_dir: Path,
        stats: dict,
        depth: int = 0,
    ) -> None:
        """递归下载某个目录下的所有资源和子目录。

        Args:
            topic_id_alias: 知识库别名 ID
            directory_id: 目录 ID
            target_dir: 本地目标目录
            stats: 统计字典（原地修改）
            depth: 递归深度（用于日志缩进）
        """
        indent = "  " * depth
        notes_dir = target_dir / "notes"
        files_dir = target_dir / "files"
        page = 1

        while True:
            logger.info("%s📄 正在拉取第 %d 页 (dir=%s)...", indent, page, directory_id)

            content = fetch_notebook_resources(
                self.token, topic_id_alias, directory_id, page=page, client=self.client
            )

            # 处理子目录（仅在第一页时，避免重复）
            if page == 1:
                directories = content.get("directories") or []
                if directories:
                    logger.info("%s  📂 发现 %d 个子目录", indent, len(directories))
                    for sub_dir in directories:
                        sub_name = sub_dir.get("name", "未命名目录")
                        sub_id = sub_dir.get("id", 0)
                        sub_target = target_dir / sanitize_filename(sub_name)
                        sub_target.mkdir(parents=True, exist_ok=True)

                        logger.info("%s  📂 进入子目录: %s", indent, sub_name)
                        self._download_directory(
                            topic_id_alias, sub_id, sub_target, stats, depth=depth + 1
                        )
                        time.sleep(self.delay)

            # 处理资源
            resources = content.get("resources", []) or []
            has_next = content.get("has_next", 0)

            if not resources and page == 1 and not (content.get("directories") or []):
                logger.info("%s  ⚠️ 该目录暂无内容。", indent)
                break

            if resources:
                logger.info("%s  本页 %d 个资源:", indent, len(resources))
                for resource in resources:
                    resource_type = resource.get("resource_type", "")
                    if resource_type == "NOTE":
                        notes_dir.mkdir(exist_ok=True)
                        self._process_note_resource(resource, notes_dir)
                        stats["notes"] += 1
                    elif resource_type == "FILE":
                        files_dir.mkdir(parents=True, exist_ok=True)
                        self._process_file_resource(resource, files_dir)
                        stats["files"] += 1
                    else:
                        logger.info("%s    ⏭ 跳过未知类型: %s", indent, resource_type)
                        stats["skipped"] += 1

            if not has_next:
                break

            page += 1
            time.sleep(self.delay)

    def download_all(self, notebooks: list[dict]) -> dict:
        """下载所有知识库的笔记。"""
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

    # ------------------------------------------------------------------
    # 资源处理
    # ------------------------------------------------------------------

    def _process_note_resource(self, resource: dict, notes_dir: Path) -> None:
        """处理笔记类型资源"""
        meta = resource.get("resource_note_meta_data", {})
        if not meta:
            return

        title = meta.get("title", "").strip() or "无标题"
        note_id = meta.get("note_id", meta.get("id", "unknown"))
        created_at = meta.get("created_at", "")

        # 优先通过 note_id 匹配已有文件夹
        existing_dir = self._existing_notes.get(note_id)
        if existing_dir and not self.force:
            md_file = existing_dir / "note.md"
            if md_file.exists():
                logger.info("    ⏭ 已存在: %s", title[:40])
                return

        # 生成新的文件夹名
        folder_name = self._make_note_folder_name(title, created_at, note_id)
        note_dir = existing_dir if existing_dir else notes_dir / folder_name

        if note_dir.exists() and not self.force:
            md_file = note_dir / "note.md"
            if md_file.exists():
                logger.info("    ⏭ 已存在: %s", title[:40])
                return

        note_dir.mkdir(parents=True, exist_ok=True)
        attachments_dir = note_dir / "attachments"

        # 下载附件
        self._download_note_attachments(meta, attachments_dir, note_dir)

        # 生成 Markdown
        md_content = self._notebook_note_to_markdown(meta, attachments_dir, note_dir)
        (note_dir / "note.md").write_text(md_content, encoding="utf-8")

        # 保存原始 JSON
        if self.save_json:
            (note_dir / "note.json").write_text(
                json.dumps(resource, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        display_title = title[:40] + "..." if len(title) > 40 else title
        logger.info("    ✨ %s", display_title)

    def _process_file_resource(self, resource: dict, files_dir: Path) -> None:
        """处理文件类型资源"""
        meta = resource.get("resource_file_meta_data", {})
        if not meta:
            return

        name = meta.get("name", "unknown_file")
        file_url = meta.get("file_url", "")

        if not file_url:
            logger.warning("    ⚠️ 文件无下载链接: %s", name)
            return

        files_dir.mkdir(parents=True, exist_ok=True)
        save_path = files_dir / sanitize_filename(name, max_length=120)

        if save_path.exists() and not self.force:
            kb = save_path.stat().st_size / 1024
            logger.info("    ⏭ 已存在: %s (%.1f KB)", name, kb)
            return

        self._download_file(file_url, save_path)

    def _download_note_attachments(
        self, meta: dict, attachments_dir: Path, note_dir: Path
    ) -> bool:
        """下载笔记类型资源的附件"""
        has = False

        # 附件（音频/链接等）
        for i, att in enumerate(meta.get("attachments", [])):
            att_url = att.get("url", "")
            att_type = att.get("type", "")
            if att_url and att_type != "link":
                has = True
                ext = get_file_extension(att_url, f".{att_type or 'bin'}")
                self._download_file(att_url, attachments_dir / f"attachment_{i + 1}{ext}")

        # 图片
        images = (
            meta.get("original_images", [])
            or meta.get("small_images", [])
        )
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
                return True

            save_path.parent.mkdir(parents=True, exist_ok=True)
            with self.client.stream("GET", url, timeout=60) as resp:
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

    # ------------------------------------------------------------------
    # Markdown 转换
    # ------------------------------------------------------------------

    def _notebook_note_to_markdown(
        self, meta: dict, attachments_dir: Path, note_dir: Path
    ) -> str:
        """将知识库笔记资源的 meta data 转为 Markdown"""
        lines = []

        title = meta.get("title", "").strip()
        if title:
            lines.append(f"# {title}")
            lines.append("")

        # 元信息
        lines.append("## 📋 笔记信息")
        lines.append("")
        lines.append("| 属性 | 值 |")
        lines.append("|------|-----|")
        lines.append(f"| ID | `{meta.get('note_id', '')}` |")
        lines.append(f"| 来源 | {meta.get('source', '')} |")
        lines.append(f"| 类型 | {meta.get('note_type', '')} |")
        lines.append(f"| 录入方式 | {meta.get('entry_type', '')} |")
        lines.append(f"| 创建时间 | {meta.get('created_at', '')} |")
        lines.append(f"| 更新时间 | {meta.get('edit_time', '')} |")
        lines.append(f"| AI 生成 | {'是' if meta.get('is_ai_generated') else '否'} |")

        tags = meta.get("tags", [])
        if tags:
            tag_names = ", ".join(f"`{t['name']}`" for t in tags if isinstance(t, dict))
            lines.append(f"| 标签 | {tag_names} |")
        lines.append("")

        # 正文
        content = meta.get("content", "").strip()
        if content:
            lines.append("## 📝 内容")
            lines.append("")
            lines.append(content)
            lines.append("")

        # 引用内容
        ref_content = meta.get("ref_content", "").strip()
        if ref_content:
            lines.append("## 📖 引用内容")
            lines.append("")
            lines.append("> " + ref_content.replace("\n", "\n> "))
            lines.append("")

        # 附件
        attachments = meta.get("attachments", [])
        if attachments:
            lines.append("## 🔊 附件")
            lines.append("")
            for i, att in enumerate(attachments):
                att_type = att.get("type", "unknown")
                att_url = att.get("url", "")
                att_title = att.get("title", "")

                if att_type == "link":
                    if att_title and att_url:
                        lines.append(f"- 🔗 [{att_title}]({att_url})")
                    elif att_url:
                        lines.append(f"- 🔗 [{att_url}]({att_url})")
                elif att_url:
                    ext = get_file_extension(att_url, f".{att_type}")
                    att_filename = f"attachment_{i + 1}{ext}"
                    att_path = attachments_dir / att_filename
                    rel_path = os.path.relpath(att_path, note_dir)
                    lines.append(f"- **{att_type.upper()}**: [{att_filename}]({rel_path})")
                else:
                    lines.append(f"- **{att_type.upper()}**: (无链接)")
            lines.append("")

        # 图片
        images = meta.get("original_images", []) or meta.get("small_images", [])
        if images:
            lines.append("## 🖼️ 图片")
            lines.append("")
            for i, img in enumerate(images):
                img_url = img if isinstance(img, str) else img.get("url", "") if isinstance(img, dict) else ""
                if img_url:
                    ext = get_file_extension(img_url, ".jpg")
                    img_filename = f"image_{i + 1}{ext}"
                    img_path = attachments_dir / img_filename
                    rel_path = os.path.relpath(img_path, note_dir)
                    lines.append(f"![图片 {i + 1}]({rel_path})")
                    lines.append("")

        # 所属知识库
        topics = meta.get("topics", [])
        if topics:
            lines.append("## 📚 所属知识库")
            lines.append("")
            for t in topics:
                if isinstance(t, dict):
                    lines.append(f"- {t.get('topic_name', '(未知)')}")
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _scan_existing_notes(self, root_dir: Path) -> None:
        """递归扫描目录下所有已存在的 note.json，建立 note_id → folder 映射。"""
        if not root_dir.exists():
            return

        for json_file in root_dir.rglob("note.json"):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                # notebook_downloader 保存的 JSON 结构是整个 resource 对象
                meta = data.get("resource_note_meta_data", data)
                note_id = meta.get("note_id", meta.get("id", ""))
                if note_id:
                    self._existing_notes[note_id] = json_file.parent
            except (json.JSONDecodeError, IOError):
                continue

        if self._existing_notes:
            logger.info("  💾 扫描到 %d 个已有笔记", len(self._existing_notes))

    def _make_note_folder_name(
        self, title: str, created_at: str, note_id: str
    ) -> str:
        """生成笔记文件夹名"""
        date_prefix = ""
        if created_at:
            try:
                dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
                date_prefix = dt.strftime("%Y%m%d_%H%M%S")
            except ValueError:
                date_prefix = created_at.replace(" ", "_").replace(":", "")

        base = f"{date_prefix}_{title}" if title else f"{date_prefix}_{note_id}"
        return sanitize_filename(base)

    def _generate_notebook_index(
        self, notebook: dict, notebook_dir: Path, stats: dict
    ) -> None:
        """生成知识库索引文件"""
        name = notebook.get("name", "未命名知识库")
        index_path = notebook_dir / "INDEX.md"

        with open(index_path, "w", encoding="utf-8") as f:
            f.write(f"# 📚 {name}\n\n")
            f.write(f"- 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- 笔记数: {stats['notes']}\n")
            f.write(f"- 文件数: {stats['files']}\n\n")

            # 列出笔记
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

            # 列出文件
            files_dir = notebook_dir / "files"
            if files_dir.exists():
                files = sorted(f_item for f_item in files_dir.iterdir() if f_item.is_file())
                if files:
                    f.write("\n## 文件列表\n\n")
                    f.write("| # | 文件名 | 大小 |\n")
                    f.write("|---|--------|------|\n")
                    for i, fi in enumerate(files, 1):
                        kb = fi.stat().st_size / 1024
                        f.write(f"| {i} | [{fi.name}](files/{fi.name}) | {kb:.1f} KB |\n")

    def _print_summary(self, total_notebooks: int) -> None:
        """打印下载总结"""
        logger.info("=" * 60)
        logger.info("📊 全部知识库下载总结")
        logger.info("=" * 60)
        logger.info("  📚 知识库数:   %d", total_notebooks)
        logger.info("  📝 笔记:       %d 篇", self.stats['notes'])
        logger.info("  📁 文件:       %d 个", self.stats['files'])
        logger.info("  ⏭  跳过:       %d 个", self.stats['skipped'])
        logger.info("  📂 输出目录:   %s", self.output_dir.resolve())
        logger.info("=" * 60)
