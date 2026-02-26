"""笔记创建模块 — 处理图片上传与笔记发布"""

import json
from pathlib import Path
from typing import Any

import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder

from getnotes_cli.auth import AuthToken
from getnotes_cli.config import IMAGE_TOKEN_API_URL, NOTE_CREATE_API_URL

class NoteCreator:
    """笔记创建器，处理图片上传和笔记创建"""

    def __init__(self, token: AuthToken):
        self.token = token
        self.headers = token.get_headers()

    def _get_image_token(self, ext: str) -> dict[str, Any]:
        """获取阿里云 OSS 上传凭证"""
        payload = {"source": "web", "type": ext.lstrip(".")}
        resp = requests.post(
            IMAGE_TOKEN_API_URL,
            headers=self.headers,
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("h", {}).get("c") != 0:
            raise RuntimeError(f"获取上传凭证失败: {data}")
        # 返回第一条凭证
        return data.get("c", [])[0]

    def upload_image(self, image_path: Path) -> dict[str, Any]:
        """上传图片到阿里云 OSS，返回图片信息（包含 access_url）"""
        if not image_path.exists():
            raise FileNotFoundError(f"图片不存在: {image_path}")

        ext = image_path.suffix.lower()
        if ext not in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
            raise ValueError(f"不支持的图片格式: {ext}")

        # 1. 获取上传凭证
        token_info = self._get_image_token(ext)
        
        # 2. 组装表单数据
        # 阿里云 OSS 要求表单字段顺序：前面的参数，最后是 file
        fields = {
            "OSSAccessKeyId": token_info["accessid"],
            "policy": token_info["policy"],
            "Signature": token_info["signature"],
            "key": token_info["object_key"],
            "callback": token_info["callback"],
            "success_action_status": "201",
            "file": (image_path.name, open(image_path, "rb"), token_info.get("oss_content_type", f"image/{ext.lstrip('.')}")),
        }

        encoder = MultipartEncoder(fields=fields)
        upload_headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": encoder.content_type,
            "User-Agent": self.headers.get("User-Agent", ""),
            "Origin": self.headers.get("Origin", ""),
            "Referer": self.headers.get("Referer", ""),
        }

        # 3. 上传到 OSS
        resp = requests.post(
            token_info["host"],
            headers=upload_headers,
            data=encoder,
            timeout=30,
        )
        resp.raise_for_status()
        
        # 得到笔记的 callback 返回的是 json
        try:
            callback_data = resp.json()
            if callback_data.get("h", {}).get("c") != 0:
                 raise RuntimeError(f"图片上传回调失败: {callback_data}")
        except json.JSONDecodeError:
             pass # 有时不会返回标准 json

        return token_info

    def _build_json_content(self, text: str, images: list[dict[str, Any]]) -> str:
        """根据文本和图片构建 ProseMirror json_content"""
        content_nodes = []
        
        # 文本段落
        if text:
            for paragraph in text.split("\\n"):
                content_nodes.append({
                    "type": "paragraph",
                    "attrs": {"lineHeight": "100%", "textAlign": None, "class": "", "indent": 0},
                    "content": [{"type": "text", "text": paragraph}] if paragraph else []
                })
        else:
             content_nodes.append({
                    "type": "paragraph",
                    "attrs": {"lineHeight": "100%", "textAlign": None, "class": "", "indent": 0},
             })
             
        # 图片节点
        for img in images:
            content_nodes.append({
                "type": "image",
                "attrs": {
                    "commentIds": None,
                    "class": "",
                    "src": img["access_url"],
                    "alt": "",
                    "title": "",
                    "width": 350,
                    "height": "auto",
                    "align": "left",
                    "href": None,
                    "target": None,
                    "data-src": None,
                    "loading": None
                }
            })
            
            # 图片后跟一个空段落
            content_nodes.append({
                "type": "paragraph",
                "attrs": {"lineHeight": "100%", "textAlign": None, "class": None, "indent": 0}
            })

        json_content = {
            "type": "doc",
            "content": content_nodes
        }
        return json.dumps(json_content, ensure_ascii=False)

    def create_note(self, text: str, image_paths: list[Path] = None) -> dict[str, Any]:
        """创建笔记"""
        image_paths = image_paths or []
        uploaded_images = []
        
        # 1. 上传所有图片
        for img_path in image_paths:
            img_info = self.upload_image(img_path)
            uploaded_images.append(img_info)

        # 2. 组装纯文本 content（末尾添加图片 markdown 语法）
        content = text
        if uploaded_images:
            content += "\\n\\n" + "\\n".join([f"![]({img['access_url']})" for img in uploaded_images])

        # 3. 组装 json_content
        json_content_str = self._build_json_content(text, uploaded_images)

        # 4. 发送创建请求
        payload = {
            "title": "",
            "content": content,
            "json_content": json_content_str,
            "entry_type": "manual",
            "note_type": "plain_text",
            "source": "web",
            "tags": []
        }

        resp = requests.post(
            NOTE_CREATE_API_URL,
            headers=self.headers,
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("h", {}).get("c") != 0:
            raise RuntimeError(f"创建笔记失败: {data}")
            
        return data.get("c", {})
