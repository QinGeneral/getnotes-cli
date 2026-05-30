"""配置与常量"""

from pathlib import Path

# ========================================================================
# API 配置
# ========================================================================

# 官方 OpenAPI
OPENAPI_BASE_URL = "https://openapi.biji.com"

OPENAPI_NOTE_SAVE_URL = f"{OPENAPI_BASE_URL}/open/api/v1/resource/note/save"
OPENAPI_NOTE_TASK_PROGRESS_URL = f"{OPENAPI_BASE_URL}/open/api/v1/resource/note/task/progress"
OPENAPI_NOTE_LIST_URL = f"{OPENAPI_BASE_URL}/open/api/v1/resource/note/list"
OPENAPI_NOTE_DETAIL_URL = f"{OPENAPI_BASE_URL}/open/api/v1/resource/note/detail"
OPENAPI_NOTE_UPDATE_URL = f"{OPENAPI_BASE_URL}/open/api/v1/resource/note/update"
OPENAPI_NOTE_DELETE_URL = f"{OPENAPI_BASE_URL}/open/api/v1/resource/note/delete"
OPENAPI_NOTE_SHARING_URL = f"{OPENAPI_BASE_URL}/open/api/v1/resource/note/sharing"
OPENAPI_IMAGE_UPLOAD_TOKEN_URL = f"{OPENAPI_BASE_URL}/open/api/v1/resource/image/upload_token"
OPENAPI_TAGS_ADD_URL = f"{OPENAPI_BASE_URL}/open/api/v1/resource/note/tags/add"
OPENAPI_TAGS_DELETE_URL = f"{OPENAPI_BASE_URL}/open/api/v1/resource/note/tags/delete"
OPENAPI_KNOWLEDGE_LIST_URL = f"{OPENAPI_BASE_URL}/open/api/v1/resource/knowledge/list"
OPENAPI_KNOWLEDGE_SUBSCRIBE_LIST_URL = f"{OPENAPI_BASE_URL}/open/api/v1/resource/knowledge/subscribe/list"
OPENAPI_KNOWLEDGE_CREATE_URL = f"{OPENAPI_BASE_URL}/open/api/v1/resource/knowledge/create"
OPENAPI_KNOWLEDGE_NOTES_URL = f"{OPENAPI_BASE_URL}/open/api/v1/resource/knowledge/notes"
OPENAPI_KNOWLEDGE_NOTE_ADD_URL = f"{OPENAPI_BASE_URL}/open/api/v1/resource/knowledge/note/batch-add"
OPENAPI_KNOWLEDGE_NOTE_REMOVE_URL = f"{OPENAPI_BASE_URL}/open/api/v1/resource/knowledge/note/remove"
OPENAPI_RECALL_URL = f"{OPENAPI_BASE_URL}/open/api/v1/resource/recall"
OPENAPI_KNOWLEDGE_RECALL_URL = f"{OPENAPI_BASE_URL}/open/api/v1/resource/recall/knowledge"

# Legacy Web API（仅用于官方 OpenAPI 未覆盖的目录树/文件资源能力）
LEGACY_NOTES_API_URL = "https://get-notes.luojilab.com/voicenotes/web/notes"

# 知识库列表 API
LEGACY_NOTEBOOKS_API_URL = "https://knowledge-api.trytalks.com/v1/web/topic/mine/list"

# 创建笔记 API
LEGACY_NOTE_CREATE_API_URL = "https://get-notes.luojilab.com/voicenotes/web/notes"

# 通过链接创建笔记流式 API
LEGACY_LINK_NOTE_CREATE_API_URL = "https://get-notes.luojilab.com/voicenotes/web/notes/stream"

# 搜索笔记 API
LEGACY_SEARCH_API_URL = "https://get-notes.luojilab.com/voicenotes/web/notes/search"

# 获取图片上传 Token API
LEGACY_IMAGE_TOKEN_API_URL = "https://get-notes.luojilab.com/voicenotes/web/token/image"

# 订阅知识库列表 API
LEGACY_SUBSCRIBE_NOTEBOOKS_API_URL = "https://knowledge-api.trytalks.com/v1/web/subscribe/topic/list"

# 知识库资源列表 API（笔记本功能）
LEGACY_KNOWLEDGE_API_URL = "https://knowledge-api.trytalks.com/v1/web/topic/resource/list/mix"

# 笔记加入知识库 API
LEGACY_ADD_TO_NOTEBOOK_API_URL = "https://get-notes.luojilab.com/voicenotes/web/topics/import/notes"

# Backward-compatible aliases used by older modules/tests.
NOTES_API_URL = LEGACY_NOTES_API_URL
NOTEBOOKS_API_URL = LEGACY_NOTEBOOKS_API_URL
NOTE_CREATE_API_URL = LEGACY_NOTE_CREATE_API_URL
LINK_NOTE_CREATE_API_URL = LEGACY_LINK_NOTE_CREATE_API_URL
SEARCH_API_URL = LEGACY_SEARCH_API_URL
IMAGE_TOKEN_API_URL = LEGACY_IMAGE_TOKEN_API_URL
SUBSCRIBE_NOTEBOOKS_API_URL = LEGACY_SUBSCRIBE_NOTEBOOKS_API_URL
KNOWLEDGE_API_URL = LEGACY_KNOWLEDGE_API_URL
ADD_TO_NOTEBOOK_API_URL = LEGACY_ADD_TO_NOTEBOOK_API_URL

# 得到笔记登录页
LOGIN_URL = "https://www.biji.com"

# API 域名（用于 CDP 请求监听）
API_DOMAINS = [
    "get-notes.luojilab.com",
    "knowledge-api.trytalks.com",
]

# 默认请求 headers
DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Content-Type": "application/json",
    "Origin": "https://www.biji.com",
    "Referer": "https://www.biji.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/145.0.0.0 Safari/537.36"
    ),
}

# ========================================================================
# 路径配置
# ========================================================================

# Auth token 缓存目录
CONFIG_DIR = Path.home() / ".getnotes-cli"

# Auth token 缓存文件
AUTH_CACHE_FILE = CONFIG_DIR / "auth.json"

# Legacy Bearer token 缓存文件（仅用于 download-tree 等 legacy-only 能力）
LEGACY_AUTH_CACHE_FILE = CONFIG_DIR / "legacy_auth.json"

# Chrome profile 目录（CDP 用）
CHROME_PROFILE_DIR = CONFIG_DIR / "chrome-profile"

# 默认下载目录
DEFAULT_OUTPUT_DIR = Path.home() / "Downloads" / "getnotes_export"

# ========================================================================
# 下载配置
# ========================================================================

# 每页拉取数量
PAGE_SIZE = 20

# 请求间隔（秒）
REQUEST_DELAY = 0.5

# 默认下载数量限制
DEFAULT_LIMIT = 100

# 缓存清单文件名
CACHE_MANIFEST_FILE = "cache_manifest.json"
