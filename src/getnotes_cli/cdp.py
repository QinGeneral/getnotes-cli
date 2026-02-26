"""Chrome DevTools Protocol (CDP) 工具 — 用于自动获取 Bearer token。

通过 CDP 启动 Chrome，打开得到笔记页面，监听网络请求以捕获 Authorization header。
"""

import json
import platform
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

from getnotes_cli.config import CHROME_PROFILE_DIR, LOGIN_URL, API_DOMAINS

_httpx = httpx.Client(timeout=10)

# CDP 端口范围
CDP_PORT_RANGE = range(9222, 9232)


# ========================================================================
# Chrome 管理
# ========================================================================


def get_chrome_path() -> str | None:
    """获取 Chrome 可执行文件路径"""
    system = platform.system()
    if system == "Darwin":
        path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        return path if Path(path).exists() else None
    elif system == "Linux":
        for candidate in ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]:
            if shutil.which(candidate):
                return candidate
        return None
    elif system == "Windows":
        path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        return path if Path(path).exists() else None
    return None


def find_available_port(start: int = 9222, attempts: int = 10) -> int:
    """查找可用端口"""
    for offset in range(attempts):
        port = start + offset
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"在 {start}-{start + attempts - 1} 范围内找不到可用端口")


def find_existing_chrome(port_range: range = CDP_PORT_RANGE) -> tuple[int | None, str | None]:
    """扫描端口范围，查找已运行的 Chrome 调试实例"""
    for port in port_range:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                continue  # 端口空闲，跳过
        except OSError:
            pass  # 端口已占用
        url = get_debugger_url(port, timeout=2)
        if url:
            return port, url
    return None, None


_chrome_process: subprocess.Popen | None = None


def launch_chrome(port: int = 9222) -> bool:
    """启动 Chrome，打开得到笔记页面"""
    global _chrome_process
    chrome_path = get_chrome_path()
    if not chrome_path:
        return False

    profile_dir = CHROME_PROFILE_DIR
    profile_dir.mkdir(parents=True, exist_ok=True)

    args = [
        chrome_path,
        f"--remote-debugging-port={port}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        f"--user-data-dir={profile_dir}",
        "--remote-allow-origins=*",
        LOGIN_URL,
    ]
    try:
        _chrome_process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except Exception:
        return False


def terminate_chrome() -> bool:
    """关闭 Chrome"""
    global _chrome_process
    if _chrome_process is None:
        return False
    try:
        _chrome_process.terminate()
        _chrome_process.wait(timeout=5)
    except Exception:
        try:
            _chrome_process.kill()
        except Exception:
            pass
    _chrome_process = None
    return True


# ========================================================================
# CDP 协议
# ========================================================================


def get_debugger_url(port: int = 9222, tries: int = 1, timeout: int = 5) -> str | None:
    """获取 Chrome 调试 WebSocket URL"""
    for attempt in range(tries):
        try:
            resp = _httpx.get(f"http://localhost:{port}/json/version", timeout=timeout)
            return resp.json().get("webSocketDebuggerUrl")
        except Exception:
            if attempt < tries - 1:
                time.sleep(1)
    return None


def execute_cdp_command(ws_url: str, method: str, params: dict | None = None) -> dict:
    """通过 WebSocket 发送 CDP 命令"""
    import websocket
    ws = websocket.create_connection(ws_url, timeout=30, suppress_origin=True)
    try:
        command = {"id": 1, "method": method, "params": params or {}}
        ws.send(json.dumps(command))
        while True:
            response = json.loads(ws.recv())
            if response.get("id") == 1:
                return response.get("result", {})
    finally:
        ws.close()


def get_current_url(ws_url: str) -> str:
    """获取当前页面 URL"""
    execute_cdp_command(ws_url, "Runtime.enable")
    result = execute_cdp_command(ws_url, "Runtime.evaluate", {"expression": "window.location.href"})
    return result.get("result", {}).get("value", "")


def navigate_to_url(ws_url: str, url: str) -> None:
    """导航到指定 URL"""
    execute_cdp_command(ws_url, "Page.enable")
    execute_cdp_command(ws_url, "Page.navigate", {"url": url})


# ========================================================================
# Token 提取（核心）
# ========================================================================


def _find_biji_page(port: int) -> dict | None:
    """查找或创建得到笔记页面"""
    try:
        resp = _httpx.get(f"http://localhost:{port}/json", timeout=5)
        pages = resp.json()
    except Exception:
        return None

    # 优先查找已有的 biji.com 页面
    for page in pages:
        url = page.get("url", "")
        if "biji.com" in url:
            return page

    # 没有则创建新标签页
    try:
        from urllib.parse import quote
        encoded = quote(LOGIN_URL, safe="")
        resp = _httpx.put(f"http://localhost:{port}/json/new?{encoded}", timeout=15)
        if resp.status_code == 200 and resp.text.strip():
            return resp.json()
    except Exception:
        pass
    return None


def extract_auth_via_cdp(
    auto_launch: bool = True,
    login_timeout: int = 300,
) -> dict[str, str] | None:
    """
    通过 CDP 监听网络请求，提取 Authorization header。

    流程：
    1. 启动 Chrome 或连接已有实例
    2. 打开得到笔记页面
    3. 等待用户登录
    4. 监听 API 请求的 Authorization header
    5. 返回 headers dict

    Returns:
        包含 Authorization 和 Xi-Csrf-Token 的 headers dict，失败返回 None
    """
    import websocket

    # 1. 查找或启动 Chrome
    port, debugger_url = find_existing_chrome()
    reused = bool(port)

    if not debugger_url and auto_launch:
        chrome_path = get_chrome_path()
        if not chrome_path:
            raise RuntimeError(
                "❌ 未找到 Chrome 浏览器。\n"
                "请安装 Google Chrome，或使用 `getnotes login --token` 手动输入 token。"
            )
        port = find_available_port()
        if not launch_chrome(port):
            raise RuntimeError("❌ 启动 Chrome 失败")
        debugger_url = get_debugger_url(port, tries=10)

    if not debugger_url:
        raise RuntimeError(f"❌ 无法连接 Chrome（端口 {port}）")

    # 2. 查找得到笔记页面
    page = _find_biji_page(port)
    if not page:
        raise RuntimeError("❌ 无法打开得到笔记页面")

    ws_url = page.get("webSocketDebuggerUrl")
    if not ws_url:
        raise RuntimeError("❌ 无法获取页面 WebSocket URL")

    # 3. 通过 CDP 网络监听捕获 Authorization header
    ws = websocket.create_connection(ws_url, timeout=30, suppress_origin=True)
    try:
        # 启用网络监听
        ws.send(json.dumps({"id": 10, "method": "Network.enable", "params": {}}))
        # 读取 enable 的响应
        while True:
            resp = json.loads(ws.recv())
            if resp.get("id") == 10:
                break

        print("⏳ 等待登录并捕获 API 请求中...")
        print(f"   请在浏览器中登录 {LOGIN_URL}")
        if reused:
            print("   （已连接到现有 Chrome 实例）")
        print(f"   超时时间: {login_timeout}s\n")

        start_time = time.time()
        captured_headers: dict[str, str] = {}

        while time.time() - start_time < login_timeout:
            try:
                ws.settimeout(2.0)
                raw = ws.recv()
                event = json.loads(raw)
            except websocket.WebSocketTimeoutException:
                continue
            except Exception:
                continue

            # 监听 Network.requestWillBeSent 事件
            if event.get("method") == "Network.requestWillBeSent":
                request = event.get("params", {}).get("request", {})
                url = request.get("url", "")
                headers = request.get("headers", {})

                # 检查是否是得到笔记的 API 请求
                is_target = any(domain in url for domain in API_DOMAINS)
                if is_target and "Authorization" in headers:
                    auth_value = headers["Authorization"]
                    if auth_value.startswith("Bearer "):
                        captured_headers["Authorization"] = auth_value
                        # 尝试捕获 CSRF token
                        for key in ["Xi-Csrf-Token", "X-Appid", "X-Av"]:
                            if key in headers:
                                captured_headers[key] = headers[key]
                        print(f"✅ 成功捕获 Authorization token!")
                        return captured_headers

        raise RuntimeError("⏰ 登录超时，未捕获到 API 请求。请重试。")

    finally:
        ws.close()
        if not reused:
            terminate_chrome()
