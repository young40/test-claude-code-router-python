from pyllms import Server
from pyllms.src.services.config import ConfigOptions

def create_server(config: dict) -> Server:
    """
    创建并返回一个服务器实例
    
    Args:
        config: 服务器配置字典
        
    Returns:
        Server: 服务器实例
    """
    # 创建 ConfigOptions 对象
    options = ConfigOptions(
        initial_config=config.get("initial_config", {}),
        json_path=config.get("json_path"),
        use_json_file="json_path" in config,
        env_path=config.get("env_path"),
        use_env_file="env_path" in config,
        use_environment_variables=True
    )
    
    # 创建服务器实例
    server = Server(options)
    return server