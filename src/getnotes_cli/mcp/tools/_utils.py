import inspect
import logging

def register_all_tools(mcp_server):
    """Dynamically register all exported tool functions from loaded modules."""
    import getnotes_cli.mcp.tools.notes as notes_tools
    import getnotes_cli.mcp.tools.notebooks as notebooks_tools
    
    modules = [notes_tools, notebooks_tools]
    
    logger = logging.getLogger("getnotes_cli.mcp.tools")
    registered_count = 0
    
    for mod in modules:
        if not hasattr(mod, "__all__"):
            logger.warning(f"Module {mod.__name__} has no __all__ defined.")
            continue
            
        for func_name in mod.__all__:
            if hasattr(mod, func_name):
                func = getattr(mod, func_name)
                if inspect.isfunction(func):
                    # Register with FastMCP
                    msg = f"Registering tool: {func_name} from {mod.__name__}"
                    logger.debug(msg)
                    try:
                        mcp_server.tool()(func)
                        registered_count += 1
                    except Exception as e:
                        logger.error(f"Failed to register {func_name}: {e}")
                        
    logger.info(f"Registered {registered_count} tools.")

# We can define a global tools registry or let fastmcp discover them
# This is a stub for potential future use cases.
