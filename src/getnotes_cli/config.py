"""配置与常量"""

from pathlib import Path

# ========================================================================
# API 配置
# ========================================================================

# 笔记列表 API（原有功能）
NOTES_API_URL = "https://get-notes.luojilab.com/voicenotes/web/notes"

# 知识库列表 API
NOTEBOOKS_API_URL = "https://knowledge-api.trytalks.com/v1/web/topic/mine/list"

# 创建笔记 API
NOTE_CREATE_API_URL = "https://get-notes.luojilab.com/voicenotes/web/notes"

# 通过链接创建笔记流式 API
LINK_NOTE_CREATE_API_URL = "https://get-notes.luojilab.com/voicenotes/web/notes/stream"

# 搜索笔记 API
SEARCH_API_URL = "https://get-notes.luojilab.com/voicenotes/web/notes/search"

# 获取图片上传 Token API
IMAGE_TOKEN_API_URL = "https://get-notes.luojilab.com/voicenotes/web/token/image"

# 订阅知识库列表 API
SUBSCRIBE_NOTEBOOKS_API_URL = "https://knowledge-api.trytalks.com/v1/web/subscribe/topic/list"

# 知识库资源列表 API（笔记本功能）
KNOWLEDGE_API_URL = "https://knowledge-api.trytalks.com/v1/web/topic/resource/list/mix"

# 笔记加入知识库 API
ADD_TO_NOTEBOOK_API_URL = "https://get-notes.luojilab.com/voicenotes/web/topics/import/notes"

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
