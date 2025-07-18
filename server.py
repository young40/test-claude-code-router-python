from pyllms import Server

def create_server(config: dict) -> Server:
    """
    创建并返回一个服务器实例
    
    Args:
        config: 服务器配置字典
        
    Returns:
        Server: 服务器实例
    """
    server = Server(config)
    return server