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
                # 使用一个更简单的中间件实现
                @self.server.app.middleware("http")
                async def middleware(request, call_next):
                    # 简单地调用处理函数，然后继续处理请求
                    if callable(handler):
                        try:
                            # 创建一个简单的响应对象
                            class SimpleResponse:
                                def __init__(self):
                                    self.status_code = 200
                                    self.body = None
                                    self.headers = {}
                            
                            response = SimpleResponse()
                            
                            # 调用处理函数
                            await handler(request, response)
                            
                            # 如果设置了错误状态码，返回错误响应
                            if response.status_code != 200:
                                from starlette.responses import Response
                                return Response(
                                    content=response.body,
                                    status_code=response.status_code,
                                    headers=response.headers
                                )
                        except Exception as e:
                            print(f"Error in middleware: {e}")
                    
                    # 继续处理请求
                    return await call_next(request)
            except Exception as e:
                print(f"Failed to add middleware: {e}")
    
    async def start(self) -> None:
        """启动服务器"""
        if hasattr(self.server, "app"):
            # 直接使用 FastAPI 应用
            import uvicorn
            import asyncio
            import threading
            
            host = self.server.config_service.get("HOST", "127.0.0.1")
            port = int(self.server.config_service.get("PORT", "3000"))
            
            print(f"✅ Server started on {host}:{port}")
            print("Press Ctrl+C to stop the server")
            
            # 创建一个新的线程来运行服务器
            def run_server():
                uvicorn.run(
                    self.server.app,
                    host=host,
                    port=port,
                    log_level="info"
                )
            
            # 在新线程中启动服务器
            server_thread = threading.Thread(target=run_server)
            server_thread.daemon = True
            server_thread.start()
            
            # 等待一段时间，确保服务器已经启动
            await asyncio.sleep(1)
        else:
            print("Server has no app attribute")


def create_server(config: dict) -> ServerAdapter:
    """
    创建并返回一个服务器实例
    
    Args:
        config: 服务器配置字典
        
    Returns:
        ServerAdapter: 服务器适配器实例
    """
    # 检查是否有调试应用程序
    debug_app = config.get("initial_config", {}).get("debug_app")
    if debug_app:
        print("使用调试应用程序")
        
        # 创建一个简单的服务器适配器
        class SimpleServer:
            def __init__(self):
                self.app = debug_app
                self.config_service = config.get("initial_config", {})
        
        # 返回适配器
        return ServerAdapter(SimpleServer())
    
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