"""MCP tools for interacting with Get 笔记 notes."""

import tempfile
from pathlib import Path

from getnotes_cli.auth import get_or_refresh_token
from getnotes_cli.config import DEFAULT_OUTPUT_DIR
from getnotes_cli.creator import NoteCreator
from getnotes_cli.downloader import NoteDownloader

# We will export the functions that should be registered
__all__ = ["download_notes", "create_note", "create_link_note"]

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
        output_lines = []
        note_id = None
        
        events = creator.create_note_from_link(url)
        for data in events:
            msg_type = data.get("msg_type")
            inner_data = data.get("data", {})
            if msg_type == -1 and "note_id" in inner_data:
                note_id = inner_data["note_id"]
        
        if note_id:
            return f"Successfully created AI note from link!\nNote ID: {note_id}"
        else:
            return "Note creation completed but no ID was returned. It may still be processing."
            
    except Exception as e:
        return f"Error creating note from link: {e}"
