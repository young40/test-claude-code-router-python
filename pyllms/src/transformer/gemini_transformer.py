import json
import asyncio
from typing import Dict, Any, Optional, List, Union
from urllib.parse import urljoin
import httpx

from ..types.transformer import Transformer, TransformerOptions
from ..types.llm import UnifiedChatRequest, UnifiedMessage, LLMProvider
from ..utils.log import log


class GeminiTransformer(Transformer):
    """Gemini转换器"""
    
    def __init__(self, options: Optional[TransformerOptions] = None):
        super().__init__(options)
        self.name = "gemini"
        self.end_point = "/v1beta/models/:modelAndAction"
    
    async def transform_request_in(
        self, 
        request: UnifiedChatRequest, 
        provider: LLMProvider
    ) -> Dict[str, Any]:
        """将统一请求格式转换为Gemini格式"""
        
        # 转换消息
        contents = []
        for message in request.messages:
            role = "model" if message.role == "assistant" else "user"
            
            parts = []
            
            # 处理内容
            if isinstance(message.content, str):
                parts.append({"text": message.content})
            elif isinstance(message.content, list):
                for content in message.content:
                    if hasattr(content, 'type') and content.type == "text":
                        parts.append({"text": getattr(content, 'text', '')})
            
            # 处理工具调用
            if hasattr(message, 'tool_calls') and message.tool_calls:
                for tool_call in message.tool_calls:
                    parts.append({
                        "functionCall": {
                            "id": tool_call.id or f"tool_{hash(str(tool_call))}"[:15],
                            "name": tool_call.function.get("name", ""),
                            "args": json.loads(tool_call.function.get("arguments", "{}"))
                        }
                    })
            
            contents.append({
                "role": role,
                "parts": parts
            })
        
        # 转换工具
        tools = []
        if hasattr(request, 'tools') and request.tools:
            function_declarations = []
            for tool in request.tools:
                if tool.type == "function":
                    func_def = tool.function.copy()
                    
                    # 清理不支持的字段
                    if "parameters" in func_def and isinstance(func_def["parameters"], dict):
                        params = func_def["parameters"]
                        if "$schema" in params:
                            del params["$schema"]
                        if "additionalProperties" in params:
                            del params["additionalProperties"]
                        
                        if "properties" in params:
                            for key, prop in params["properties"].items():
                                if isinstance(prop, dict):
                                    if "$schema" in prop:
                                        del prop["$schema"]
                                    if "additionalProperties" in prop:
                                        del prop["additionalProperties"]
                                    
                                    if "items" in prop and isinstance(prop["items"], dict):
                                        if "$schema" in prop["items"]:
                                            del prop["items"]["$schema"]
                                        if "additionalProperties" in prop["items"]:
                                            del prop["items"]["additionalProperties"]
                                    
                                    if (prop.get("type") == "string" and 
                                        "format" in prop and 
                                        prop["format"] not in ["enum", "date-time"]):
                                        del prop["format"]
                    
                    function_declarations.append({
                        "name": func_def.get("name", ""),
                        "description": func_def.get("description", ""),
                        "parameters": func_def.get("parameters", {})
                    })
            
            if function_declarations:
                tools.append({"functionDeclarations": function_declarations})
        
        # 构建请求体
        body = {
            "contents": contents,
            "tools": tools
        }
        
        # 构建URL
        action = "streamGenerateContent?alt=sse" if request.stream else "generateContent"
        url = urljoin(provider.base_url, f"./{request.model}:{action}")
        
        # 构建配置
        config = {
            "url": url,
            "headers": {
                "x-goog-api-key": provider.api_key,
                "Authorization": None
            }
        }
        
        return {
            "body": body,
            "config": config
        }
    
    async def transform_request_out(self, request: Dict[str, Any]) -> UnifiedChatRequest:
        """将Gemini格式转换为统一请求格式"""
        contents = request.get("contents", [])
        tools = request.get("tools", [])
        model = request.get("model", "")
        max_tokens = request.get("max_tokens")
        temperature = request.get("temperature")
        stream = request.get("stream")
        tool_choice = request.get("tool_choice")
        
        # 转换消息
        messages = []
        for content in contents:
            if isinstance(content, str):
                messages.append({
                    "role": "user",
                    "content": content
                })
            elif isinstance(content, dict):
                if content.get("role") == "user":
                    parts = content.get("parts", [])
                    message_content = []
                    for part in parts:
                        if "text" in part:
                            message_content.append({
                                "type": "text",
                                "text": part.get("text", "")
                            })
                    
                    messages.append({
                        "role": "user",
                        "content": message_content
                    })
                elif content.get("role") == "model":
                    parts = content.get("parts", [])
                    message_content = []
                    for part in parts:
                        if "text" in part:
                            message_content.append({
                                "type": "text", 
                                "text": part.get("text", "")
                            })
                    
                    messages.append({
                        "role": "assistant",
                        "content": message_content
                    })
        
        # 转换工具
        unified_tools = []
        for tool in tools:
            if "functionDeclarations" in tool:
                for func_decl in tool["functionDeclarations"]:
                    unified_tools.append({
                        "type": "function",
                        "function": {
                            "name": func_decl.get("name", ""),
                            "description": func_decl.get("description", ""),
                            "parameters": func_decl.get("parameters", {})
                        }
                    })
        
        return UnifiedChatRequest(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=stream,
            tools=unified_tools if unified_tools else None,
            tool_choice=tool_choice
        )
    
    async def transform_response_out(self, response: httpx.Response) -> httpx.Response:
        """转换响应输出"""
        content_type = response.headers.get("Content-Type", "")
        
        if "application/json" in content_type:
            # 处理非流式响应
            json_response = await response.json()
            
            # 提取工具调用
            tool_calls = []
            if json_response.get("candidates") and len(json_response["candidates"]) > 0:
                parts = json_response["candidates"][0].get("content", {}).get("parts", [])
                for part in parts:
                    if "functionCall" in part:
                        tool_calls.append({
                            "id": part["functionCall"].get("id", f"tool_{hash(str(part))}"[:15]),
                            "type": "function",
                            "function": {
                                "name": part["functionCall"].get("name", ""),
                                "arguments": json.dumps(part["functionCall"].get("args", {}))
                            }
                        })
            
            # 构建OpenAI格式响应
            openai_response = {
                "id": json_response.get("responseId", ""),
                "choices": [{
                    "finish_reason": json_response.get("candidates", [{}])[0].get("finishReason", "").lower() or None,
                    "index": 0,
                    "message": {
                        "content": "\n".join([
                            part.get("text", "") for part in 
                            json_response.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                            if "text" in part
                        ]),
                        "role": "assistant",
                        "tool_calls": tool_calls if tool_calls else None
                    }
                }],
                "created": int(asyncio.get_event_loop().time()),
                "model": json_response.get("modelVersion", ""),
                "object": "chat.completion",
                "usage": {
                    "completion_tokens": json_response.get("usageMetadata", {}).get("candidatesTokenCount", 0),
                    "prompt_tokens": json_response.get("usageMetadata", {}).get("promptTokenCount", 0),
                    "total_tokens": json_response.get("usageMetadata", {}).get("totalTokenCount", 0)
                }
            }
            
            return httpx.Response(
                status_code=response.status_code,
                headers=response.headers,
                json=openai_response
            )
            
        elif "stream" in content_type:
            # 处理流式响应
            if not hasattr(response, 'aiter_bytes'):
                return response
            
            async def stream_generator():
                async for chunk in response.aiter_bytes():
                    chunk_str = chunk.decode('utf-8')
                    
                    if chunk_str.startswith("data: "):
                        chunk_str = chunk_str[6:].strip()
                    else:
                        continue
                    
                    try:
                        log("gemini chunk:", chunk_str)
                        chunk_data = json.loads(chunk_str)
                        
                        # 提取工具调用
                        tool_calls = []
                        if chunk_data.get("candidates") and len(chunk_data["candidates"]) > 0:
                            parts = chunk_data["candidates"][0].get("content", {}).get("parts", [])
                            for part in parts:
                                if "functionCall" in part:
                                    tool_calls.append({
                                        "id": part["functionCall"].get("id", f"tool_{hash(str(part))}"[:15]),
                                        "type": "function",
                                        "function": {
                                            "name": part["functionCall"].get("name", ""),
                                            "arguments": json.dumps(part["functionCall"].get("args", {}))
                                        }
                                    })
                        
                        # 构建OpenAI格式流响应
                        openai_chunk = {
                            "choices": [{
                                "delta": {
                                    "role": "assistant",
                                    "content": "\n".join([
                                        part.get("text", "") for part in 
                                        chunk_data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                                        if "text" in part
                                    ]),
                                    "tool_calls": tool_calls if tool_calls else None
                                },
                                "finish_reason": chunk_data.get("candidates", [{}])[0].get("finishReason", "").lower() or None,
                                "index": chunk_data.get("candidates", [{}])[0].get("index", 1 if tool_calls else 0),
                                "logprobs": None
                            }],
                            "created": int(asyncio.get_event_loop().time()),
                            "id": chunk_data.get("responseId", ""),
                            "model": chunk_data.get("modelVersion", ""),
                            "object": "chat.completion.chunk",
                            "system_fingerprint": "fp_a49d71b8a1"
                        }
                        
                        log("gemini response:", json.dumps(openai_chunk, indent=2))
                        yield f"data: {json.dumps(openai_chunk)}\n\n".encode('utf-8')
                        
                    except json.JSONDecodeError as e:
                        log(f"Error parsing Gemini chunk: {e}")
                        continue
            
            return httpx.Response(
                status_code=response.status_code,
                headers={
                    "Content-Type": content_type,
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive"
                },
                content=b''.join([chunk async for chunk in stream_generator()])
            )
        
        return response