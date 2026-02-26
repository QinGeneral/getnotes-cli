"""用户配置持久化管理 — 保存到 ~/.getnotes-cli/config.json"""

import json
from pathlib import Path
from typing import Any, Optional

from getnotes_cli.config import CONFIG_DIR

CONFIG_FILE = CONFIG_DIR / "config.json"

# 允许持久化的配置项及其类型转换
ALLOWED_KEYS = {
    "output": str,
    "delay": float,
    "page_size": int,
}

# CLI 参数名 -> 配置文件 key 的映射（处理连字符）
CLI_KEY_MAP = {
    "page-size": "page_size",
    "output": "output",
    "delay": "delay",
}


class UserSettings:
    """读写 ~/.getnotes-cli/config.json 的管理器"""

    def __init__(self) -> None:
        self._data: dict[str, Any] = self._load()

    # ------------------------------------------------------------------
    # 读写
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        if CONFIG_FILE.exists():
            try:
                return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def get(self, key: str) -> Optional[Any]:
        """获取某项配置值，不存在返回 None"""
        return self._data.get(key)

    def all(self) -> dict[str, Any]:
        """返回所有已保存的配置"""
        return dict(self._data)

    def set(self, key: str, value: str) -> Any:
        """设置配置项，自动做类型转换。返回转换后的值。"""
        canon_key = CLI_KEY_MAP.get(key, key)
        if canon_key not in ALLOWED_KEYS:
            raise KeyError(
                f"不支持的配置项 '{key}'，可选: {', '.join(sorted(CLI_KEY_MAP.keys()))}"
            )
        converter = ALLOWED_KEYS[canon_key]
        converted = converter(value)
        self._data[canon_key] = converted
        self._save()
        return converted

    def remove(self, key: str) -> bool:
        """删除某项配置，返回是否存在并已删除"""
        canon_key = CLI_KEY_MAP.get(key, key)
        if canon_key in self._data:
            del self._data[canon_key]
            self._save()
            return True
        return False

    def clear(self) -> int:
        """清除所有配置，返回清除的条目数"""
        count = len(self._data)
        self._data.clear()
        self._save()
        return count


# ------------------------------------------------------------------
# 便捷函数：解析最终值（命令行 > 配置文件 > 默认值）
# ------------------------------------------------------------------

_settings = None


def _get_settings() -> UserSettings:
    global _settings
    if _settings is None:
        _settings = UserSettings()
    return _settings


def resolve_output(cli_value: Optional[str], default: str) -> str:
    """解析 output 的最终值"""
    if cli_value is not None:
        return cli_value
    saved = _get_settings().get("output")
    return saved if saved is not None else default


def resolve_delay(cli_value: Optional[float], default: float) -> float:
    """解析 delay 的最终值"""
    if cli_value is not None:
        return cli_value
    saved = _get_settings().get("delay")
    return saved if saved is not None else default


def resolve_page_size(cli_value: Optional[int], default: int) -> int:
    """解析 page_size 的最终值"""
    if cli_value is not None:
        return cli_value
    saved = _get_settings().get("page_size")
    return saved if saved is not None else default
