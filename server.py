from pyllms import Server
from pyllms.src.services.config import ConfigOptions
from typing import Any

def create_server(config: Any) -> Server:
    """
    Create and return a Server instance, similar to ccr/src/server.ts
    Args:
        config: Server configuration
    Returns:
        Server: The server instance
    """
    return Server(config)