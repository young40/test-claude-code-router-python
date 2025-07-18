from pyllms import Server
from pyllms.src.services.config import ConfigOptions
from typing import Any

def create_server(config: Any) -> Server:
    """
    Create and return a Server instance, similar to ccr/src/server.ts
    Args:
        config: Server configuration (dict)
    Returns:
        Server: The server instance
    """
    options = ConfigOptions(
        initial_config=config.get("initial_config"),
        json_path=config.get("json_path"),
        use_json_file="json_path" in config,
        env_path=config.get("env_path"),
        use_env_file="env_path" in config,
        use_environment_variables=True
    )
    return Server(options)