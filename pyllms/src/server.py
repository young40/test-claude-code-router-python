from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import signal
import sys

from .services.config import ConfigService
from .services.llm import LLMService
from .services.provider import ProviderService
from .services.transformer import TransformerService
from .utils.log import log
from .api.middleware import error_handler
from .api.routes import register_api_routes


def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    app = FastAPI()
    
    # 注册CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    return app


class Server:
    """服务器类"""
    
    def __init__(self, options=None):
        if options is None:
            options = {}
            
        self.config_service = ConfigService(options)
        self.transformer_service = TransformerService(self.config_service)
        
        # 初始化转换器服务
        self.transformer_service.initialize()
        
        # 初始化提供者服务和LLM服务
        self.provider_service = ProviderService(self.config_service, self.transformer_service)
        self.llm_service = LLMService(self.provider_service)
        
        # 创建FastAPI应用
        self.app = create_app()
        
        # 存储服务器实例到应用状态中
        self.app.state._server = self
    
    async def start(self):
        """启动服务器"""
        try:
            # 添加预处理钩子
            @self.app.middleware("http")
            async def model_provider_middleware(request: Request, call_next):
                if request.method == "POST":
                    try:
                        body = await request.json()
                        if not body or "model" not in body:
                            return Response(
                                content='{"error": "Missing model in request body"}',
                                status_code=400,
                                media_type="application/json"
                            )
                        
                        provider, model = body["model"].split(",")
                        body["model"] = model
                        request.state.provider = provider
                        
                        # 重新构建请求体
                        async def receive_modified():
                            return {"type": "http.request", "body": body}
                        
                        request._receive = receive_modified
                    except Exception as err:
                        log(f"Error in model_provider_middleware: {err}")
                        return Response(
                            content='{"error": "Internal server error"}',
                            status_code=500,
                            media_type="application/json"
                        )
                
                response = await call_next(request)
                return response
            
            # 注册错误处理器
            @self.app.exception_handler(Exception)
            async def exception_handler(request: Request, exc: Exception):
                return await error_handler(exc, request)
            
            # 注册API路由
            register_api_routes(self.app)
            
            # 获取配置的端口和主机
            port = int(self.config_service.get("PORT", "3000"))
            host = self.config_service.get("HOST", "127.0.0.1")
            
            # 设置关闭信号处理
            def shutdown(sig, frame):
                log(f"Received {signal.Signals(sig).name}, shutting down gracefully...")
                sys.exit(0)
            
            signal.signal(signal.SIGINT, shutdown)
            signal.signal(signal.SIGTERM, shutdown)
            
            # 启动服务器
            log(f"🚀 LLMs API server listening on http://{host}:{port}")
            uvicorn.run(self.app, host=host, port=port)
            
        except Exception as error:
            log(f"Error starting server: {error}")
            sys.exit(1)