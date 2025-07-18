from typing import Dict, List, Any, Optional
from fastapi import FastAPI, Request, Response, Depends, HTTPException, Body
from fastapi.responses import JSONResponse, StreamingResponse
import httpx
from datetime import datetime
import json

from ..types.llm import UnifiedChatRequest, RegisterProviderRequest, LLMProvider
from ..utils.request import send_unified_request
from ..utils.log import log
from .middleware import create_api_error


def register_api_routes(app: FastAPI) -> None:
    """注册API路由"""
    
    # 健康检查和信息端点
    @app.get("/")
    async def root():
        return {"message": "LLMs API", "version": "1.0.0"}
    
    @app.get("/health")
    async def health():
        return {"status": "ok", "timestamp": datetime.now().isoformat()}
    
    # 获取转换器列表
    transformers_with_endpoint = app.state._server.transformer_service.get_transformers_with_endpoint()
    log(f"可用的转换器: {[item['name'] for item in transformers_with_endpoint]}")
    
    # 不再注册特定端点，只使用通配符路由
    
    # 添加一个通配符路由，捕获所有请求
    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
    async def catch_all(request: Request, path: str):
        log(f"捕获到请求: {request.method} {request.url}")
        log(f"路径: {path}")
        log(f"查询参数: {request.query_params}")
        log(f"请求头: {request.headers}")
        
        # 如果是 /v1/messages 请求，尝试处理
        if path == "v1/messages" or path.startswith("v1/messages"):
            log("尝试处理 Anthropic 请求")
            
            # 获取 Anthropic 转换器
            anthropic_transformer = None
            for item in transformers_with_endpoint:
                if item["name"] == "Anthropic":
                    anthropic_transformer = item["transformer"]
                    log(f"找到 Anthropic 转换器: {anthropic_transformer}")
                    break
            
            if anthropic_transformer:
                log("调用 process_transformer_request 处理请求")
                return await process_transformer_request(request, anthropic_transformer)
        
        # 返回 404 错误，但包含详细信息
        log(f"未找到匹配的路由: {path}")
        return Response(
            content=f'{{"error": "Not Found", "path": "{path}", "method": "{request.method}"}}',
            status_code=404,
            media_type="application/json"
        )
    
    # 处理转换器请求的函数
    async def process_transformer_request(request: Request, transformer):
        log(f"开始处理转换器请求: URL={request.url}, 转换器={transformer.name if hasattr(transformer, 'name') else '未知'}")
        try:
            body = await request.json()
            log(f"请求体: {json.dumps(body, ensure_ascii=False)}")
            
            provider_name = getattr(request.state, "provider", None)
            log(f"提供者名称: {provider_name}")
            
            if not provider_name:
                provider_name = "ollama"  # 默认提供者
                log(f"使用默认提供者: {provider_name}")
            
            provider = app.state._server.provider_service.get_provider(provider_name)
            log(f"获取到提供者: {provider}")
            
            if not provider:
                log(f"未找到提供者: {provider_name}")
                raise create_api_error(
                    f"Provider '{provider_name}' not found",
                    404,
                    "provider_not_found"
                )
            
            request_body = body
            config = {}
            
            # 转换请求输出
            log("开始转换请求输出")
            if hasattr(transformer, 'transform_request_out') and callable(transformer.transform_request_out):
                log("调用 transform_request_out")
                transform_out = await transformer.transform_request_out(body)
                if hasattr(transform_out, 'body'):
                    request_body = transform_out.body
                    config = transform_out.config or {}
                    log(f"转换后的请求体: {json.dumps(request_body, ensure_ascii=False)}")
                else:
                    request_body = transform_out
                    log(f"转换后的请求体: {json.dumps(request_body, ensure_ascii=False)}")
            
            # 应用提供者转换器
            log('use transformers:', provider.get('transformer', {}).get('use', []))
            if provider.get('transformer', {}).get('use'):
                for t in provider['transformer']['use']:
                    if not t or not hasattr(t, 'transform_request_in'):
                        continue
                    
                    transform_in = await t.transform_request_in(request_body, provider)
                    if hasattr(transform_in, 'body'):
                        request_body = transform_in.body
                        config = {**config, **(transform_in.config or {})}
                    else:
                        request_body = transform_in
            
            # 应用模型特定转换器
            if (provider.get('transformer', {}).get(body['model'], {}).get('use')):
                for t in provider['transformer'][body['model']]['use']:
                    if not t or not hasattr(t, 'transform_request_in'):
                        continue
                    
                    request_body = await t.transform_request_in(request_body, provider)
            
            # 发送请求
            url = config.get('url') or provider['base_url']
            log(f"发送请求到: {url}")
            response = await send_unified_request(url, request_body, {
                'https_proxy': app.state._server.config_service.get_https_proxy(),
                **config,
                'headers': {
                    'Authorization': f"Bearer {provider['api_key']}",
                    **(config.get('headers') or {})
                }
            })
            
            if not response.status_code == 200:
                error_text = await response.text()
                log(f"Error response from {url}: {error_text}")
                raise create_api_error(
                    f"Error from provider: {error_text}",
                    response.status_code,
                    "provider_response_error"
                )
            
            # 处理响应
            final_response = response
            
            # 应用提供者转换器
            if provider.get('transformer', {}).get('use'):
                for t in provider['transformer']['use']:
                    if not t or not hasattr(t, 'transform_response_out'):
                        continue
                    
                    final_response = await t.transform_response_out(final_response)
            
            # 应用模型特定转换器
            if (provider.get('transformer', {}).get(body['model'], {}).get('use')):
                for t in provider['transformer'][body['model']]['use']:
                    if not t or not hasattr(t, 'transform_response_out'):
                        continue
                    
                    final_response = await t.transform_response_out(final_response)
            
            # 应用转换器响应输入
            if hasattr(transformer, 'transform_response_in'):
                final_response = await transformer.transform_response_in(final_response)
            
            # 返回响应
            if not final_response.status_code == 200:
                return Response(
                    content=await final_response.read(),
                    status_code=final_response.status_code,
                    headers=dict(final_response.headers)
                )
            
            is_stream = body.get('stream', False)
            if is_stream:
                return StreamingResponse(
                    final_response.iter_bytes(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive"
                    }
                )
            else:
                return Response(
                    content=await final_response.read(),
                    media_type="application/json"
                )
        except Exception as e:
            log(f"处理请求时出错: {e}")
            return Response(
                content=f'{{"error": "Error processing request: {str(e)}"}}',
                status_code=500,
                media_type="application/json"
            )
    
    # 提供者管理端点
    @app.post("/providers")
    async def create_provider(request: RegisterProviderRequest):
        # 验证
        if not request.name or not request.name.strip():
            raise create_api_error("Provider name is required", 400, "invalid_request")
        
        if not request.base_url or not is_valid_url(request.base_url):
            raise create_api_error("Valid base URL is required", 400, "invalid_request")
        
        if not request.api_key or not request.api_key.strip():
            raise create_api_error("API key is required", 400, "invalid_request")
        
        if not request.models or len(request.models) == 0:
            raise create_api_error("At least one model is required", 400, "invalid_request")
        
        # 检查提供者是否已存在
        if app.state._server.provider_service.get_provider(request.name):
            raise create_api_error(
                f"Provider with name '{request.name}' already exists",
                400,
                "provider_exists"
            )
        
        provider = app.state._server.provider_service.register_provider(request)
        return provider
    
    @app.get("/providers")
    async def get_providers():
        return app.state._server.provider_service.get_providers()
    
    @app.get("/providers/{id}")
    async def get_provider(id: str):
        provider = app.state._server.provider_service.get_provider(id)
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")
        return provider
    
    @app.put("/providers/{id}")
    async def update_provider(id: str, updates: Dict[str, Any]):
        provider = app.state._server.provider_service.update_provider(id, updates)
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")
        return provider
    
    @app.delete("/providers/{id}")
    async def delete_provider(id: str):
        success = app.state._server.provider_service.delete_provider(id)
        if not success:
            raise HTTPException(status_code=404, detail="Provider not found")
        return {"message": "Provider deleted successfully"}
    
    @app.patch("/providers/{id}/toggle")
    async def toggle_provider(id: str, body: Dict[str, bool]):
        enabled = body.get("enabled", False)
        success = app.state._server.provider_service.toggle_provider(id, enabled)
        if not success:
            raise HTTPException(status_code=404, detail="Provider not found")
        return {
            "message": f"Provider {'enabled' if enabled else 'disabled'} successfully"
        }


def is_valid_url(url: str) -> bool:
    """检查URL是否有效"""
    try:
        httpx.URL(url)
        return True
    except:
        return False