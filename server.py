from pyllms import Server
from pyllms.src.services.config import ConfigOptions
from typing import Dict, Any, Callable, List, Tuple

class ServerAdapter:
    """
    服务器适配器类，用于适配不同的 API
    """
    
    def __init__(self, server: Server):
        self.server = server
        self.hooks: List[Tuple[str, Callable]] = []
    
    def add_hook(self, hook_type: str, handler: Callable) -> None:
        """
        添加钩子处理函数
        
        Args:
            hook_type: 钩子类型
            handler: 处理函数
        """
        self.hooks.append((hook_type, handler))
        
        # 如果是 FastAPI 的中间件，可以尝试添加
        if hook_type == "pre_handler" and hasattr(self.server, "app"):
            try:
                @self.server.app.middleware("http")
                async def middleware(request, call_next):
                    # 调用处理函数
                    if callable(handler):
                        await handler(request, None)
                    return await call_next(request)
            except Exception as e:
                print(f"Failed to add middleware: {e}")
    
    async def start(self) -> None:
        """启动服务器"""
        if hasattr(self.server, "start"):
            if callable(self.server.start):
                # 创建一个新的事件循环来运行服务器
                import asyncio
                import threading
                
                def run_server():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(self.server.start())
                    except Exception as e:
                        print(f"Error in server thread: {e}")
                    finally:
                        loop.close()
                
                # 在新线程中启动服务器
                server_thread = threading.Thread(target=run_server)
                server_thread.daemon = True
                server_thread.start()
            else:
                print("Server.start is not callable")
        else:
            print("Server has no start method")


def create_server(config: dict) -> ServerAdapter:
    """
    创建并返回一个服务器实例
    
    Args:
        config: 服务器配置字典
        
    Returns:
        ServerAdapter: 服务器适配器实例
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
    
    # 创建并返回适配器
    return ServerAdapter(server)