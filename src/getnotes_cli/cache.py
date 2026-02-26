"""缓存管理 — 跟踪已下载笔记的版本与状态"""

import json
from pathlib import Path

from getnotes_cli.config import CACHE_MANIFEST_FILE, CONFIG_DIR


class CacheManager:
    """管理下载缓存清单"""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.cache_path = CONFIG_DIR / CACHE_MANIFEST_FILE
        self._manifest: dict = {}

    def load(self) -> dict:
        """加载缓存清单"""
        if self.cache_path.exists():
            try:
                self._manifest = json.loads(self.cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, IOError):
                print("⚠️  缓存清单损坏，将重新构建。")
                self._manifest = {}
        return self._manifest

    def save(self) -> None:
        """保存缓存清单"""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(self._manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def is_cached(self, note: dict) -> bool:
        """检查笔记是否已缓存且版本未变化"""
        note_id = note.get("note_id", note.get("id", ""))
        if note_id not in self._manifest:
            return False
        cached = self._manifest[note_id]
        return (
            cached.get("version") == note.get("version")
            and cached.get("updated_at") == note.get("updated_at")
        )

    def update(self, note_id: str, info: dict) -> None:
        """更新缓存条目"""
        self._manifest[note_id] = info

    def get(self, note_id: str) -> dict | None:
        """获取缓存条目"""
        return self._manifest.get(note_id)

    @property
    def count(self) -> int:
        return len(self._manifest)

    @property
    def manifest(self) -> dict:
        return self._manifest

    def check(self) -> dict:
        """检查缓存状态，返回统计信息"""
        if not self.cache_path.exists():
            return {"exists": False, "count": 0, "path": str(self.cache_path)}
        self.load()
        return {
            "exists": True,
            "count": self.count,
            "path": str(self.cache_path),
            "notes": {
                nid: {
                    "title": info.get("title", "(无标题)"),
                    "created_at": info.get("created_at", ""),
                    "folder": info.get("folder_name", ""),
                }
                for nid, info in self._manifest.items()
            },
        }

    def rebuild_from_disk(self, notes_dir: Path) -> int:
        """从磁盘已有文件夹重建缓存清单。

        扫描 notes_dir 下所有子目录的 note.json，提取 note_id 等信息
        建立 note_id → folder_name 的映射。

        Returns:
            重建的缓存条目数
        """
        if not notes_dir.exists():
            return 0

        rebuilt = 0
        for folder in notes_dir.iterdir():
            if not folder.is_dir():
                continue
            json_file = folder / "note.json"
            if not json_file.exists():
                continue
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                note_id = data.get("note_id", data.get("id", ""))
                if not note_id:
                    continue
                # 避免覆盖已有缓存条目
                if note_id in self._manifest:
                    continue
                self._manifest[note_id] = {
                    "version": data.get("version"),
                    "updated_at": data.get("updated_at", ""),
                    "folder_name": folder.name,
                    "title": data.get("title", ""),
                    "created_at": data.get("created_at", ""),
                }
                rebuilt += 1
            except (json.JSONDecodeError, IOError):
                continue

        if rebuilt > 0:
            self.save()
            print(f"💾 从磁盘重建缓存: 恢复了 {rebuilt} 条记录")

        return rebuilt

    def clear(self) -> int:
        """清除缓存，返回清除的条目数"""
        count = 0
        if self.cache_path.exists():
            self.load()
            count = self.count
            self.cache_path.unlink()
        self._manifest = {}
        return count
