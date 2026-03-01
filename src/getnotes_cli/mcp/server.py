"""GetNotes MCP Server.

This server exposes tools to manage "Get 笔记" directly from an LLM client.
"""

import argparse
import logging
import os

from fastmcp import FastMCP

from getnotes_cli import __version__

# Initialize MCP server
mcp = FastMCP(
    name="getnotes",
    instructions="""GetNotes MCP - Manage "Get 笔记" notes.

Tools available:
- get_recent_notes(limit=10): Fetch recent notes' metadata and content directly without saving to disk.
- download_notes(limit=10): Download recent notes as Markdown files.
- create_note(content): Create a new note from text content.
- create_link_note(url): Use AI to create a deep note from a link URL.
- search_notes(query): Search notes by keyword and return matching results with full content.
- read_note(note_id): Read the full Markdown content of a specific note by its ID.
- list_notebooks(): Get a list of the user's notebooks with IDs.
- download_notebook(notebook_id): Download a specific notebook.
- list_subscribed_notebooks(): List subscribed notebooks.
- download_subscribed_notebook(notebook_id): Download a subscribed notebook.
- add_note_to_notebook(note_id, notebook_id): Add an existing note to a notebook.

Recommended workflow:
1. Use search_notes() to find notes by keyword.
2. Use read_note(note_id) to read the full content of a specific note.
3. Use add_note_to_notebook() to organize notes into knowledge bases.

Auth details: The auth is handled by the `getnotes-cli`. Users must run `getnotes login` in their terminal before the MCP server can execute operations on their behalf.
""",
)

mcp_logger = logging.getLogger("getnotes_cli.mcp")


def _register_tools():
    """Import and register all tools from the modular tools package."""
    from .tools._utils import register_all_tools
    
    # Import all tool modules to populate the registry
    from .tools import (  # noqa: F401
        notes,
        notebooks,
    )
    
    # Register collected tools with mcp
    register_all_tools(mcp)


# Register tools on import
_register_tools()


def main():
    """Run the MCP server."""
    parser = argparse.ArgumentParser(
        description="GetNotes MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--transport", "-t",
        choices=["stdio", "sse"],
        default=os.environ.get("GETNOTES_MCP_TRANSPORT", "stdio"),
        help="Transport protocol (default: stdio)"
    )
    parser.add_argument(
        "--host", "-H",
        default=os.environ.get("GETNOTES_MCP_HOST", "127.0.0.1"),
        help="Host to bind for SSE (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=int(os.environ.get("GETNOTES_MCP_PORT", "8000")),
        help="Port for SSE transport (default: 8000)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=os.environ.get("GETNOTES_MCP_DEBUG", "").lower() == "true",
        help="Enable debug logging"
    )
    
    args = parser.parse_args()
    
    if args.debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        mcp_logger.setLevel(logging.DEBUG)
    
    if args.transport == "stdio":
        mcp.run()
    elif args.transport == "sse":
        mcp.run(
            transport="sse",
            host=args.host,
            port=args.port,
        )


if __name__ == "__main__":
    main()
