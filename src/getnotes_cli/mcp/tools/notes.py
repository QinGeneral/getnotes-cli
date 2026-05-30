"""MCP tools for interacting with Get 笔记 notes."""

import json
import tempfile
from pathlib import Path

from getnotes_cli.auth import get_or_refresh_token
from getnotes_cli.config import DEFAULT_OUTPUT_DIR
from getnotes_cli.creator import NoteCreator
from getnotes_cli.downloader import NoteDownloader
from getnotes_cli.downloader import _normalize_openapi_note
from getnotes_cli.markdown import note_to_markdown
from getnotes_cli.openapi_client import OpenAPIClient
from getnotes_cli.searcher import NoteSearcher

# We will export the functions that should be registered
__all__ = ["download_notes", "create_note", "create_link_note", "search_notes", "read_note", "get_recent_notes"]

def download_notes(limit: int = 10, force: bool = False) -> str:
    """Download the most recent notes to the default output directory.
    
    Args:
        limit: Number of notes to download (default: 10). Maximum is 100.
        force: Whether to force re-download bypassing cache (default: False)
        
    Returns:
        A string summarizing the download results.
    """
    if limit > 100:
        limit = 100
        
    try:
        auth = get_or_refresh_token()
    except Exception as e:
        return f"Error: Authentication failed. Please run 'getnotes login' in your terminal. ({e})"
        
    output_dir = DEFAULT_OUTPUT_DIR
    downloader = NoteDownloader(
        token=auth,
        output_dir=output_dir,
        limit=limit,
        force=force,
    )
    
    try:
        stats = downloader.run()
        return (
            f"Successfully checked {downloader.total_processed} recent notes.\n"
            f"- New: {stats['new']}\n"
            f"- Updated: {stats['updated']}\n"
            f"- Cached (Skipped): {stats['cached']}\n"
            f"Notes are saved at {output_dir.resolve()}/notes/"
        )
    except Exception as e:
        return f"Error downloading notes: {e}"

def get_recent_notes(limit: int = 10) -> str:
    """Fetch the most recent notes directly from the cloud without downloading to local disk.
    
    Args:
        limit: Number of recent notes to fetch (default: 10). Maximum is 100.
        
    Returns:
        A JSON string containing the recent notes' metadata and content.
    """
    if limit > 100:
        limit = 100
        
    try:
        auth = get_or_refresh_token()
    except Exception as e:
        return f"Error: Authentication failed. Please run 'getnotes login' in your terminal. ({e})"
        
    try:
        notes_list = []
        cursor = ""
        with OpenAPIClient(auth, min_interval=1.0) as client:
            while len(notes_list) < limit:
                data = client.list_notes(cursor)
                notes_list.extend(data.get("notes", []) or [])
                if not data.get("has_more"):
                    break
                cursor = data.get("cursor", "")
                if not cursor:
                    break
        notes_list = notes_list[:limit]
        
        notes = []
        for item in notes_list:
            # Clean title
            title = item.get("title", "").strip()
            
            # Extract content
            note_content = item.get("content", "").strip()
            ref_content = item.get("ref_content", "").strip()
            
            # Clean tags
            tags = [
                t if isinstance(t, str) else t.get("name", "")
                for t in item.get("tags", [])
                if isinstance(t, str) or t.get("type") != "system"
            ]
            
            note_data = {
                "note_id": item.get("note_id", item.get("id", "")),
                "title": title,
                "note_type": item.get("note_type", ""),
                "content": note_content,
                "ref_content": ref_content,
                "tags": tags,
                "created_at": item.get("created_at", ""),
            }
            notes.append(note_data)
            
        return json.dumps({"notes": notes, "fetched_count": len(notes)}, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error fetching recent notes: {e}"

def create_note(content: str) -> str:
    """Create a new 'Get 笔记' note from text or markdown content.
    
    Args:
        content: The text/markdown content of the note.
        
    Returns:
        A formatted string with the result and note ID.
    """
    try:
        auth = get_or_refresh_token()
    except Exception as e:
        return f"Error: Authentication failed. Please run 'getnotes login' in your terminal. ({e})"
        
    creator = NoteCreator(auth)
    
    try:
        data = creator.create_note(content)
        note_id = data.get("note_id", "unknown")
        created_at = data.get("created_at", "unknown time")
        return f"Successfully created note!\nID: {note_id}\nCreated at: {created_at}"
    except Exception as e:
        return f"Error creating note: {e}"

def create_link_note(url: str) -> str:
    """Create a new 'Get 笔记' note from a web link using AI analysis.
    
    Args:
        url: The web URL to analyze and turn into a note.
        
    Returns:
        A summary of the AI generation process and the final note ID.
    """
    try:
        auth = get_or_refresh_token()
    except Exception as e:
        return f"Error: Authentication failed. Please run 'getnotes login' in your terminal. ({e})"
        
    creator = NoteCreator(auth)
    
    try:
        note_id = None
        
        data = creator.create_note_from_link(url)
        note_id = data.get("note_id")
        
        if note_id:
            return f"Successfully created AI note from link!\nNote ID: {note_id}"
        else:
            return "Note creation completed but no ID was returned. It may still be processing."
            
    except Exception as e:
        return f"Error creating note from link: {e}"

def search_notes(query: str, page: int = 1, page_size: int = 10) -> str:
    """Search for notes by keyword and return matching results.

    Args:
        query: The search keyword or phrase to find relevant notes.
        page: Page number (starting from 1, default: 1).
        page_size: Number of results per page (default: 10).
        
    Returns:
        A formatted string with matching notes including titles, types, tags, and snippets.
    """
    try:
        auth = get_or_refresh_token()
    except Exception as e:
        return f"Error: Authentication failed. Please run 'getnotes login' in your terminal. ({e})"
        
    searcher = NoteSearcher(auth)
    
    try:
        result = searcher.search(query, page=page, page_size=page_size)
    except Exception as e:
        return f"Error searching notes: {e}"
    
    items = result["items"]
    total = result["total"]
    has_more = result["has_more"]
    
    if not items:
        return f"No notes found matching '{query}'."
    
    notes = []
    for item in items:
        # Clean highlight tags from title
        title = NoteSearcher.strip_highlight(item.get("title", "").strip())
        
        # Extract full content and ref_content, clean hl tags
        content = NoteSearcher.strip_highlight(item.get("content", "").strip())
        ref_content = NoteSearcher.strip_highlight(item.get("ref_content", "").strip())
        
        # Extract highlight snippet for quick context
        highlight = item.get("highlight_info", {})
        snippet = ""
        for key in ("title", "content", "ref_content"):
            parts = highlight.get(key, [])
            text = next((p for p in parts if p.strip()), "")
            if text:
                snippet = NoteSearcher.strip_highlight(text).strip()
                break
        
        # Clean tags (filter out system tags)
        tags = [
            NoteSearcher.strip_highlight(t if isinstance(t, str) else t.get("name", ""))
            for t in item.get("tags", [])
            if isinstance(t, str) or t.get("type") != "system"
        ]
        
        note_data = {
            "note_id": item.get("note_id", ""),
            "title": title,
            "note_type": item.get("note_type", ""),
            "content": content,
            "ref_content": ref_content,
            "tags": tags,
            "created_at": item.get("created_at", ""),
            "source": item.get("source", ""),
            "highlight_snippet": snippet,
        }
        notes.append(note_data)
    
    response = {
        "query": query,
        "total": total,
        "page": page,
        "has_more": has_more,
        "notes": notes,
    }
    
    return json.dumps(response, ensure_ascii=False, indent=2)


def read_note(note_id: str) -> str:
    """Read the full content of a specific note by its ID.

    First looks in local downloaded files (using the cache manifest).
    Falls back to searching if the note isn't found locally.

    Args:
        note_id: The unique note ID (e.g. from search_notes results).

    Returns:
        The full Markdown content of the note, or an error message.
    """
    from getnotes_cli.cache import CacheManager

    cache = CacheManager(DEFAULT_OUTPUT_DIR)
    cache.load()

    info = cache.get(note_id)
    if info:
        folder_name = info.get("folder_name", "")
        if folder_name:
            md_file = DEFAULT_OUTPUT_DIR / "notes" / folder_name / "note.md"
            if md_file.exists():
                return md_file.read_text(encoding="utf-8")

    # 未在本地找到，尝试通过官方详情 API 获取内容
    try:
        auth = get_or_refresh_token()
    except Exception as e:
        return f"Error: Authentication failed. Please run 'getnotes login'. ({e})"

    try:
        with OpenAPIClient(auth) as client:
            note = _normalize_openapi_note(client.note_detail(note_id))
        return note_to_markdown(note, DEFAULT_OUTPUT_DIR / "attachments", DEFAULT_OUTPUT_DIR)
    except Exception as e:
        return f"Error reading note: {e}"
