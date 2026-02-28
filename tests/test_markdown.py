"""Tests for getnotes_cli.markdown module"""

import pytest
from pathlib import Path

from getnotes_cli.markdown import (
    sanitize_filename,
    get_file_extension,
    format_duration,
    note_to_markdown,
)


class TestSanitizeFilename:
    def test_removes_illegal_chars(self):
        # 9 illegal chars: < > : " / \ | ? *
        assert sanitize_filename('foo<>:"/\\|?*bar') == "foo_________bar"

    def test_removes_newlines_and_tabs(self):
        assert sanitize_filename("foo\nbar\ttab") == "foo_bar_tab"

    def test_strips_leading_trailing_spaces_and_dots(self):
        assert sanitize_filename("  ..hello.. ") == "hello"

    def test_truncates_long_name(self):
        long_name = "a" * 100
        result = sanitize_filename(long_name, max_length=80)
        assert len(result) == 80

    def test_custom_max_length(self):
        name = "a" * 50
        result = sanitize_filename(name, max_length=20)
        assert len(result) == 20

    def test_empty_string_returns_untitled(self):
        assert sanitize_filename("") == "untitled"

    def test_empty_after_strip_returns_untitled(self):
        # Illegal chars become underscores (not stripped), so only spaces/dots trigger fallback
        assert sanitize_filename("   ") == "untitled"
        assert sanitize_filename("...") == "untitled"

    def test_normal_name_unchanged(self):
        assert sanitize_filename("my-note_2024") == "my-note_2024"

    def test_chinese_characters_preserved(self):
        assert sanitize_filename("我的笔记") == "我的笔记"

    def test_truncated_name_strips_trailing_spaces(self):
        # If truncation leaves trailing spaces, they should be stripped
        name = "a" * 78 + "  "
        result = sanitize_filename(name, max_length=80)
        assert not result.endswith(" ")


class TestGetFileExtension:
    def test_simple_url_with_jpg(self):
        url = "https://example.com/image.jpg"
        assert get_file_extension(url) == ".jpg"

    def test_url_with_query_string(self):
        url = "https://example.com/audio.mp3?token=abc"
        assert get_file_extension(url) == ".mp3"

    def test_url_with_no_extension_returns_default(self):
        url = "https://example.com/path/noext"
        assert get_file_extension(url, ".bin") == ".bin"

    def test_url_with_no_extension_empty_default(self):
        url = "https://example.com/path/noext"
        assert get_file_extension(url) == ""

    def test_url_encoded_path(self):
        url = "https://example.com/path%2Fimage.png"
        assert get_file_extension(url) == ".png"

    def test_png_extension(self):
        url = "https://cdn.example.com/images/photo.PNG"
        assert get_file_extension(url) == ".PNG"


class TestFormatDuration:
    def test_zero_returns_empty(self):
        assert format_duration(0) == ""

    def test_negative_returns_empty(self):
        assert format_duration(-1) == ""

    def test_seconds_only(self):
        assert format_duration(5000) == "5秒"

    def test_minutes_and_seconds(self):
        assert format_duration(90000) == "1分30秒"

    def test_hours_minutes_seconds(self):
        assert format_duration(3661000) == "1小时1分1秒"

    def test_exactly_one_minute(self):
        assert format_duration(60000) == "1分0秒"

    def test_exactly_one_hour(self):
        assert format_duration(3600000) == "1小时0分0秒"

    def test_less_than_one_second(self):
        # 500 ms -> 0 seconds -> "0秒" (only ms <= 0 returns "")
        assert format_duration(500) == "0秒"


class TestNoteToMarkdown:
    def setup_method(self):
        self.note_dir = Path("/tmp/note")
        self.attachments_dir = Path("/tmp/note/attachments")

    def _make_note(self, **kwargs):
        base = {
            "note_id": "abc123",
            "title": "Test Note",
            "content": "Some content",
            "source": "app",
            "note_type": "text",
            "entry_type": "manual",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
            "is_ai_generated": False,
        }
        base.update(kwargs)
        return base

    def test_title_rendered(self):
        note = self._make_note(title="My Note")
        md = note_to_markdown(note, self.attachments_dir, self.note_dir)
        assert "# My Note" in md

    def test_no_title_skips_heading(self):
        note = self._make_note(title="")
        md = note_to_markdown(note, self.attachments_dir, self.note_dir)
        # "## " headings exist, but no h1 "# " line at start
        assert not any(line.startswith("# ") for line in md.splitlines())

    def test_content_rendered(self):
        note = self._make_note(content="Hello World")
        md = note_to_markdown(note, self.attachments_dir, self.note_dir)
        assert "Hello World" in md

    def test_no_content_skips_section(self):
        note = self._make_note(content="")
        md = note_to_markdown(note, self.attachments_dir, self.note_dir)
        assert "## 📝 内容" not in md

    def test_ref_content_rendered(self):
        note = self._make_note(ref_content="Quoted text")
        md = note_to_markdown(note, self.attachments_dir, self.note_dir)
        assert "> Quoted text" in md

    def test_tags_rendered(self):
        note = self._make_note(tags=[{"name": "python"}, {"name": "testing"}])
        md = note_to_markdown(note, self.attachments_dir, self.note_dir)
        assert "`python`" in md
        assert "`testing`" in md

    def test_link_attachment_rendered(self):
        note = self._make_note(
            attachments=[{"type": "link", "url": "https://example.com", "title": "Example"}]
        )
        md = note_to_markdown(note, self.attachments_dir, self.note_dir)
        assert "[Example](https://example.com)" in md

    def test_audio_attachment_rendered(self):
        note = self._make_note(
            attachments=[{"type": "audio", "url": "https://example.com/file.mp3", "duration": 60000}]
        )
        md = note_to_markdown(note, self.attachments_dir, self.note_dir)
        assert "AUDIO" in md
        assert "1分0秒" in md

    def test_image_from_original_images(self):
        note = self._make_note(original_images=["https://example.com/photo.jpg"])
        md = note_to_markdown(note, self.attachments_dir, self.note_dir)
        assert "![图片 1]" in md

    def test_res_info_rendered(self):
        note = self._make_note(res_info={"title": "Source", "url": "https://src.example.com"})
        md = note_to_markdown(note, self.attachments_dir, self.note_dir)
        assert "[Source](https://src.example.com)" in md

    def test_topics_rendered(self):
        note = self._make_note(topics=[{"topic_name": "Dev Notes"}])
        md = note_to_markdown(note, self.attachments_dir, self.note_dir)
        assert "Dev Notes" in md

    def test_is_ai_generated_true(self):
        note = self._make_note(is_ai_generated=True)
        md = note_to_markdown(note, self.attachments_dir, self.note_dir)
        assert "| AI 生成 | 是 |" in md

    def test_is_ai_generated_false(self):
        note = self._make_note(is_ai_generated=False)
        md = note_to_markdown(note, self.attachments_dir, self.note_dir)
        assert "| AI 生成 | 否 |" in md

    def test_metadata_table_always_present(self):
        note = self._make_note()
        md = note_to_markdown(note, self.attachments_dir, self.note_dir)
        assert "## 📋 笔记信息" in md
        assert "| 属性 | 值 |" in md
