import httpx
import json
import asyncio
from typing import Dict, Any, Optional, Union

from ..types.llm import UnifiedChatRequest
from .log import log


async def send_unified_request(
    url: Union[str, httpx.URL],
    request: UnifiedChatRequest,
    config: Dict[str, Any]
) -> httpx.Response:
    """
    发送统一请求到LLM提供者
    
    参数:
        url: 请求URL
        request: 请求数据
        config: 配置选项
    
    返回:
        httpx.Response: HTTP响应
    """
    # 设置请求头
    headers = {
        "Content-Type": "application/json",
    }
    
    if config.get("headers"):
        headers.update(config["headers"])
    
    # 设置超时
    timeout = httpx.Timeout(config.get("TIMEOUT", 60 * 60), connect=30.0)
    
    # 准备请求选项
    request_options = {
        "headers": headers,
        "timeout": timeout,
        "follow_redirects": True
    }
    
    # 添加代理
    if config.get("https_proxy"):
        request_options["proxies"] = {
            "http://": config["https_proxy"],
            "https://": config["https_proxy"]
        }
    
    # 序列化请求体
    if isinstance(request, dict):
        body = json.dumps(request)
    else:
        body = json.dumps(request.__dict__)
    
    # 记录请求信息
    log("final request:", str(url), config.get("https_proxy"), request_options)
    
    # 发送请求
    async with httpx.AsyncClient(**request_options) as client:
        response = await client.post(url, content=body)
        return response