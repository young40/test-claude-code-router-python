from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import signal
import sys
import json

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
            # 添加请求日志中间件
            @self.app.middleware("http")
            async def request_logger_middleware(request: Request, call_next):
                # 记录请求信息
                log(f"收到请求: {request.method} {request.url}")
                log(f"请求头: {dict(request.headers)}")
                log(f"查询参数: {dict(request.query_params)}")
                
                # 尝试读取请求体
                if request.method in ["POST", "PUT", "PATCH"]:
                    try:
                        # 保存原始接收函数
                        original_receive = request._receive
                        
                        # 读取请求体
                        body_bytes = await request.body()
                        
                        # 尝试解析为 JSON
                        try:
                            body = json.loads(body_bytes)
                            log(f"请求体 (JSON): {json.dumps(body, ensure_ascii=False)}")
                        except:
                            log(f"请求体 (原始): {body_bytes.decode('utf-8', errors='replace')}")
                        
                        # 重新构建请求体，以便后续处理
                        async def receive_modified():
                            return {"type": "http.request", "body": body_bytes}
                        
                        request._receive = receive_modified
                    except Exception as e:
                        log(f"读取请求体时出错: {e}")
                
                # 处理请求
                log("调用下一个处理函数")
                response = await call_next(request)
                log(f"响应状态码: {response.status_code}")
                
                # 尝试读取响应体
                try:
                    response_body = b""
                    async for chunk in response.body_iterator:
                        response_body += chunk
                    
                    # 尝试解析为 JSON
                    try:
                        response_json = json.loads(response_body)
                        log(f"响应体 (JSON): {json.dumps(response_json, ensure_ascii=False)}")
                    except:
                        log(f"响应体 (原始): {response_body.decode('utf-8', errors='replace')}")
                    
                    # 重新构建响应
                    return Response(
                        content=response_body,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        media_type=response.media_type
                    )
                except Exception as e:
                    log(f"读取响应体时出错: {e}")
                
                return response
            
            # 添加模型提供者中间件
            @self.app.middleware("http")
            async def model_provider_middleware(request: Request, call_next):
                if request.method == "POST":
                    try:
                        # 尝试解析请求体
                        try:
                            body_bytes = await request.body()
                            body = json.loads(body_bytes)
                        except Exception as e:
                            log(f"无法解析请求体: {e}")
                            # 如果无法解析请求体，继续处理请求
                            return await call_next(request)
                        
                        # 如果请求体中没有 model 字段，继续处理请求
                        if not body or "model" not in body:
                            log("请求体中没有 model 字段")
                            return await call_next(request)
                        
                        # 尝试拆分 model 字段
                        model_value = body["model"]
                        log(f"Model 值: {model_value}")
                        
                        if "," in model_value:
                            provider, model = model_value.split(",", 1)
                            body["model"] = model
                            request.state.provider = provider
                            log(f"拆分后: provider={provider}, model={model}")
                            
                            # 重新构建请求体
                            body_bytes = json.dumps(body).encode("utf-8")
                            async def receive_modified():
                                return {"type": "http.request", "body": body_bytes}
                            
                            request._receive = receive_modified
                        else:
                            # 如果 model 字段不是以 provider,model 的格式提供的，使用默认提供者
                            request.state.provider = "ollama"  # 使用默认提供者
                            log(f"使用默认提供者: ollama, model={model_value}")
                    except Exception as err:
                        log(f"Error in model_provider_middleware: {err}")
                        # 继续处理请求，不要中断
                
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