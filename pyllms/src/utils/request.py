import httpx
import json
import asyncio
from typing import Dict, Any, Optional, Union

from ..types.llm import UnifiedChatRequest
from .log import log


async def send_unified_request(
    url: Union[str, httpx.URL],
    request: Union[UnifiedChatRequest, Dict[str, Any]],
    config: Dict[str, Any]
) -> httpx.Response:
    """
    Send unified request to LLM provider
    
    Args:
        url: Request URL
        request: Request data (either UnifiedChatRequest object or dictionary)
        config: Configuration options
    
    Returns:
        httpx.Response: HTTP response
    
    Raises:
        ApiError: If there's an error during the request
    """
    try:
        # Set request headers
        headers = {
            "Content-Type": "application/json",
        }
        
        if config.get("headers"):
            headers.update(config["headers"])
        
        # Set timeout
        timeout = httpx.Timeout(config.get("TIMEOUT", 60 * 60), connect=30.0)
        
        # Prepare request options
        request_options = {
            "headers": headers,
            "timeout": timeout,
            "follow_redirects": True
        }
        
        # Add proxy if configured
        if config.get("https_proxy"):
            request_options["proxies"] = {
                "http://": config["https_proxy"],
                "https://": config["https_proxy"]
            }
        
        # Check if this is a streaming request
        is_stream = False
        if isinstance(request, dict) and request.get("stream") is True:
            is_stream = True
        elif hasattr(request, "stream") and request.stream is True:
            is_stream = True
        
        # Serialize request body based on type
        try:
            if isinstance(request, dict):
                body = json.dumps(request)
            elif hasattr(request, 'to_dict') and callable(request.to_dict):
                # Use the to_dict method if available (preferred for UnifiedChatRequest)
                body = json.dumps(request.to_dict())
            elif hasattr(request, '__dict__'):
                # Fallback to __dict__ for other objects
                body = json.dumps(request.__dict__)
            elif hasattr(request, 'to_json') and callable(request.to_json):
                # Support to_json method if available
                body = request.to_json()
            else:
                # Last resort, try direct serialization
                body = json.dumps(request)
        except Exception as e:
            log(f"Error serializing request: {e}")
            from ..api.middleware import create_api_error
            raise create_api_error(
                f"Failed to serialize request: {str(e)}",
                400,
                "invalid_request_format"
            )
        
        # Log request information
        log("Final request:", str(url), config.get("https_proxy"), {
            "headers": headers,
            "body_length": len(body) if body else 0,
            "is_stream": is_stream
        })
        
        # Send request
        try:
            async with httpx.AsyncClient(**request_options) as client:
                if is_stream:
                    async with client.stream("POST", url, content=body) as response:
                        # 读取所有内容（错误或正常流）
                        content = ""
                        async for chunk in response.aiter_text():
                            content += chunk
                        # 构造一个简单的 httpx.Response-like 对象或直接返回内容
                        return content
                else:
                    response = await client.post(url, content=body)
                    return response
        except httpx.RequestError as e:
            log(f"Request error: {e}")
            from ..api.middleware import create_api_error
            raise create_api_error(
                f"Failed to connect to provider: {str(e)}",
                503,
                "provider_connection_error"
            )
        except httpx.TimeoutException as e:
            log(f"Request timeout: {e}")
            from ..api.middleware import create_api_error
            raise create_api_error(
                "Request to provider timed out",
                504,
                "provider_timeout"
            )
    except Exception as e:
        # Catch any other exceptions that weren't handled above
        log(f"Unexpected error in send_unified_request: {e}")
        from ..api.middleware import create_api_error
        if not hasattr(e, 'status_code'):  # Only re-raise if not already an ApiError
            raise create_api_error(
                f"Error sending request: {str(e)}",
                500,
                "request_error"
            )
        raise