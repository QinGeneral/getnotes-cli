"""Tests for getnotes_cli.searcher module"""

import pytest

from getnotes_cli.searcher import NoteSearcher


class TestStripHighlight:
    def test_removes_open_and_close_hl_tags(self):
        assert NoteSearcher.strip_highlight("<hl>hello</hl>") == "hello"

    def test_removes_multiple_hl_tags(self):
        text = "foo <hl>bar</hl> baz <hl>qux</hl>"
        assert NoteSearcher.strip_highlight(text) == "foo bar baz qux"

    def test_no_hl_tags_unchanged(self):
        assert NoteSearcher.strip_highlight("plain text") == "plain text"

    def test_empty_string(self):
        assert NoteSearcher.strip_highlight("") == ""

    def test_only_hl_tags_returns_empty(self):
        assert NoteSearcher.strip_highlight("<hl></hl>") == ""

    def test_nested_content_preserved(self):
        assert NoteSearcher.strip_highlight("<hl>Python 编程</hl>") == "Python 编程"


class TestExtractHighlight:
    def test_removes_hl_tags(self):
        result = NoteSearcher.extract_highlight("<hl>keyword</hl> found here")
        assert result == "keyword found here"

    def test_strips_whitespace(self):
        result = NoteSearcher.extract_highlight("  hello  ")
        assert result == "hello"

    def test_truncates_long_text(self):
        long_text = "a" * 200
        result = NoteSearcher.extract_highlight(long_text)
        assert result == "a" * 120 + "..."

    def test_text_exactly_120_chars_not_truncated(self):
        text = "x" * 120
        result = NoteSearcher.extract_highlight(text)
        assert result == text
        assert not result.endswith("...")

    def test_text_shorter_than_120_not_truncated(self):
        text = "short text"
        result = NoteSearcher.extract_highlight(text)
        assert result == "short text"

    def test_escaped_newlines_converted(self):
        result = NoteSearcher.extract_highlight("line1\\nline2")
        assert "\n" in result

    def test_multiple_hl_tags_removed(self):
        text = "<hl>first</hl> middle <hl>second</hl>"
        result = NoteSearcher.extract_highlight(text)
        assert result == "first middle second"

    def test_empty_string_returns_empty(self):
        assert NoteSearcher.extract_highlight("") == ""

    def test_truncation_applied_after_tag_removal(self):
        # Build a string where tags add length; final text without tags should be 130 chars
        inner = "a" * 130
        text = f"<hl>{inner}</hl>"
        result = NoteSearcher.extract_highlight(text)
        assert result == "a" * 120 + "..."
