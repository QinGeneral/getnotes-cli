"""MCP tools for interacting with Get 笔记 notebooks (knowledge bases)."""

from pathlib import Path

from getnotes_cli.auth import get_or_refresh_token
from getnotes_cli.config import DEFAULT_OUTPUT_DIR
from getnotes_cli.notebook import fetch_notebooks, fetch_subscribed_notebooks
from getnotes_cli.notebook_downloader import NotebookDownloader

__all__ = ["list_notebooks", "list_subscribed_notebooks", "download_notebook", "download_subscribed_notebook", "add_note_to_notebook"]

def list_notebooks() -> str:
    """List all knowledge bases (notebooks) created by the user.
    
    Returns:
        A formatted string listing the notebooks with their IDs and item counts.
    """
    try:
        auth = get_or_refresh_token()
    except Exception as e:
        return f"Error: Authentication failed. Please run 'getnotes login' in your terminal. ({e})"
        
    try:
        notebooks = fetch_notebooks(auth)
        if not notebooks:
            return "You have no notebooks."
            
        lines = [f"Found {len(notebooks)} notebooks:"]
        for i, nb in enumerate(notebooks, 1):
            name = nb.get("name", "(Unnamed)")
            count = nb.get("extend_data", {}).get("all_resource_count", 0)
            id_alias = nb.get("id_alias", "")
            lines.append(f"{i}. {name} (ID: {id_alias}) - {count} items")
            
        return "\n".join(lines)
    except Exception as e:
        return f"Error fetching notebooks: {e}"

def list_subscribed_notebooks() -> str:
    """List all knowledge bases (notebooks) subscribed by the user.
    
    Returns:
        A formatted string listing the subscribed notebooks with their IDs.
    """
    try:
        auth = get_or_refresh_token()
    except Exception as e:
        return f"Error: Authentication failed. Please run 'getnotes login' in your terminal. ({e})"
        
    try:
        notebooks = fetch_subscribed_notebooks(auth)
        if not notebooks:
            return "You have no subscribed notebooks."
            
        lines = [f"Found {len(notebooks)} subscribed notebooks:"]
        for i, nb in enumerate(notebooks, 1):
            name = nb.get("name", "(Unnamed)")
            creator = nb.get("creator", "Unknown")
            count = nb.get("extend_data", {}).get("all_resource_count", 0)
            id_alias = nb.get("id_alias", "")
            lines.append(f"{i}. {name} (by {creator}) (ID: {id_alias}) - {count} items")
            
        return "\n".join(lines)
    except Exception as e:
        return f"Error fetching subscribed notebooks: {e}"

def download_notebook(notebook_id: str, force: bool = False) -> str:
    """Download all notes from a specific user notebook by its ID.
    
    Args:
        notebook_id: The ID (id_alias) of the notebook to download. Get this from list_notebooks.
        force: Whether to force re-download bypassing cache.
        
    Returns:
        A summary of the download operation.
    """
    try:
        auth = get_or_refresh_token()
    except Exception as e:
        return f"Error: Authentication failed. Please run 'getnotes login' in your terminal. ({e})"
        
    try:
        notebooks = fetch_notebooks(auth)
        target = next((nb for nb in notebooks if nb.get("id_alias") == notebook_id), None)
        
        if not target:
            return f"Error: Could not find notebook with ID '{notebook_id}'."
            
        downloader = NotebookDownloader(
            token=auth,
            output_dir=DEFAULT_OUTPUT_DIR,
            force=force,
        )
        
        name = target.get("name", "")
        stats = downloader.download_notebook(target)
        
        return (
            f"Successfully downloaded notebook '{name}'\n"
            f"- Notes: {stats['notes']}\n"
            f"- Files: {stats['files']}\n"
            f"- Skipped: {stats['skipped']}\n"
            f"Saved to {DEFAULT_OUTPUT_DIR.resolve()}/notebooks/"
        )
    except Exception as e:
        return f"Error downloading notebook: {e}"

def download_subscribed_notebook(notebook_id: str, force: bool = False) -> str:
    """Download all notes from a specific user-subscribed notebook by its ID.
    
    Args:
        notebook_id: The ID (id_alias) of the subscribed notebook. Get this from list_subscribed_notebooks.
        force: Whether to force re-download bypassing cache.
        
    Returns:
        A summary of the download operation.
    """
    try:
        auth = get_or_refresh_token()
    except Exception as e:
        return f"Error: Authentication failed. Please run 'getnotes login' in your terminal. ({e})"
        
    try:
        notebooks = fetch_subscribed_notebooks(auth)
        target = next((nb for nb in notebooks if nb.get("id_alias") == notebook_id), None)
        
        if not target:
            return f"Error: Could not find subscribed notebook with ID '{notebook_id}'."
            
        downloader = NotebookDownloader(
            token=auth,
            output_dir=DEFAULT_OUTPUT_DIR,
            force=force,
        )
        
        name = target.get("name", "")
        creator = target.get("creator", "")
        stats = downloader.download_notebook(target)
        
        return (
            f"Successfully downloaded subscribed notebook '{name}' by {creator}\n"
            f"- Notes: {stats['notes']}\n"
            f"- Files: {stats['files']}\n"
            f"- Skipped: {stats['skipped']}\n"
            f"Saved to {DEFAULT_OUTPUT_DIR.resolve()}/notebooks/"
        )
    except Exception as e:
        return f"Error downloading subscribed notebook: {e}"

def add_note_to_notebook(note_id: str, notebook_id: str) -> str:
    """Add an existing note to a specific notebook (knowledge base).

    Args:
        note_id: The note ID to add (from search_notes or download_notes results).
        notebook_id: The notebook ID alias (from list_notebooks results).

    Returns:
        A success or error message.
    """
    try:
        auth = get_or_refresh_token()
    except Exception as e:
        return f"Error: Authentication failed. Please run 'getnotes login' in your terminal. ({e})"

    try:
        notebooks = fetch_notebooks(auth)
        target = next((nb for nb in notebooks if nb.get("id_alias") == notebook_id), None)

        if not target:
            return (
                f"Error: Notebook with ID '{notebook_id}' not found.\n"
                f"Use list_notebooks() to get valid notebook IDs."
            )

        topic_id = target.get("id")
        root_dir = target.get("root_dir", {})
        directory_id = root_dir.get("id")

        if not topic_id or not directory_id:
            return f"Error: Could not retrieve topic_id or directory_id for notebook '{notebook_id}'."

        from getnotes_cli.notebook import add_note_to_notebook as _api_add
        result = _api_add(auth, note_id, topic_id, directory_id)

        header = result.get("h", {})
        if header.get("c") == 0:
            nb_name = target.get("name", notebook_id)
            return f"Successfully added note '{note_id}' to notebook '{nb_name}'."
        else:
            return f"API returned an unexpected response: {result}"
    except Exception as e:
        return f"Error adding note to notebook: {e}"
