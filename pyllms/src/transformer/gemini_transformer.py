import json
import asyncio
import time
from typing import Dict, Any, Optional, List, Union
from urllib.parse import urljoin
import httpx

from ..types.transformer import Transformer, TransformerOptions
from ..types.llm import UnifiedChatRequest, UnifiedMessage, LLMProvider
from ..utils.log import log


class GeminiTransformer(Transformer):
    """Gemini transformer"""
    
    def __init__(self, options: Optional[TransformerOptions] = None):
        super().__init__(options)
        self.name = "gemini"
        self.end_point = "/v1beta/models/:modelAndAction"
    
    async def transform_request_in(
        self, 
        request: UnifiedChatRequest, 
        provider: LLMProvider
    ) -> Dict[str, Any]:
        """Transform unified request format to Gemini format"""
        
        # Convert messages
        contents = []
        for message in request.messages:
            # Determine role
            if message.role == "assistant":
                role = "model"
            elif message.role in ["user", "system", "tool"]:
                role = "user"
            else:
                role = "user"  # Default to user if role is not recognized
            
            parts = []
            
            # Handle content
            if isinstance(message.content, str):
                parts.append({"text": message.content})
            elif isinstance(message.content, list):
                for content in message.content:
                    if hasattr(content, 'type') and content.type == "text":
                        parts.append({"text": getattr(content, 'text', '')})
            
            # Handle tool calls
            if hasattr(message, 'tool_calls') and message.tool_calls:
                for tool_call in message.tool_calls:
                    tool_id = tool_call.id or f"tool_{hash(str(tool_call))}"[:15]
                    parts.append({
                        "functionCall": {
                            "id": tool_id,
                            "name": tool_call.function.get("name", ""),
                            "args": json.loads(tool_call.function.get("arguments", "{}"))
                        }
                    })
            
            contents.append({
                "role": role,
                "parts": parts
            })
        
        # Convert tools
        tools = []
        if hasattr(request, 'tools') and request.tools:
            function_declarations = []
            for tool in request.tools:
                if tool.type == "function":
                    # Create a copy to avoid modifying the original
                    func_def = {
                        "name": tool.function.get("name", ""),
                        "description": tool.function.get("description", ""),
                        "parameters": tool.function.get("parameters", {}).copy() if tool.function.get("parameters") else {}
                    }
                    
                    # Clean up unsupported fields
                    if "parameters" in func_def and isinstance(func_def["parameters"], dict):
                        params = func_def["parameters"]
                        if "$schema" in params:
                            del params["$schema"]
                        if "additionalProperties" in params:
                            del params["additionalProperties"]
                        
                        if "properties" in params and params["properties"]:
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
                                    
                                    if prop.get("type") == "string" and "format" in prop:
                                        if prop["format"] not in ["enum", "date-time"]:
                                            del prop["format"]
                    
                    function_declarations.append(func_def)
            
            if function_declarations:
                tools.append({"functionDeclarations": function_declarations})
        
        # Build request body
        body = {
            "contents": contents,
            "tools": tools
        }
        
        # Build URL
        action = "streamGenerateContent?alt=sse" if request.stream else "generateContent"
        url = urljoin(provider.base_url, f"./{request.model}:{action}")
        
        # Build config
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
        """Transform Gemini format to unified request format"""
        contents = request.get("contents", [])
        tools = request.get("tools", [])
        model = request.get("model", "")
        max_tokens = request.get("max_tokens")
        temperature = request.get("temperature")
        stream = request.get("stream")
        tool_choice = request.get("tool_choice")
        
        # Convert messages
        messages = []
        for content in contents:
            if isinstance(content, str):
                messages.append({
                    "role": "user",
                    "content": content
                })
            elif isinstance(content, dict) and "text" in content:
                messages.append({
                    "role": "user",
                    "content": content.get("text", "") or None
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
        
        # Convert tools
        unified_tools = []
        if tools:
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
        
        # Create unified request
        unified_request = UnifiedChatRequest(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=stream,
            tools=unified_tools if unified_tools else None,
            tool_choice=tool_choice
        )
        
        return unified_request
    
    async def transform_response_out(self, response: httpx.Response) -> httpx.Response:
        """Transform Gemini response to OpenAI format"""
        content_type = response.headers.get("Content-Type", "")
        
        if "application/json" in content_type:
            # Handle non-streaming response
            json_response = await response.json()
            
            # Extract tool calls
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
            
            # Build OpenAI format response
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
                "created": int(time.time()),
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
            # Handle streaming response
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
                        
                        # Extract tool calls
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
                        
                        # Build OpenAI format streaming response
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
                                "index": chunk_data.get("candidates", [{}])[0].get("index", 0) or (1 if tool_calls else 0),
                                "logprobs": None
                            }],
                            "created": int(time.time()),
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
            
            # Create a streaming response
            return httpx.Response(
                status_code=response.status_code,
                headers={
                    "Content-Type": "text/event-stream",
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive"
                },
                stream=stream_generator()
            )
        
        return response