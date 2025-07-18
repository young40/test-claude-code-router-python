import json
import httpx
from typing import Dict, Any, List, Optional, Union

from ..types.transformer import Transformer, TransformerOptions
from ..types.llm import UnifiedChatRequest, UnifiedMessage, UnifiedTool, LLMProvider
from ..utils.log import log


class OpenAITransformer(Transformer):
    """OpenAI转换器"""
    
    def __init__(self, options: Optional[TransformerOptions] = None):
        super().__init__(options)
        self.name = "OpenAI"
        self.end_point = "/v1/chat/completions"
    
    async def transform_request_in(
        self, 
        request: Dict[str, Any], 
        provider: LLMProvider
    ) -> Dict[str, Any]:
        """将统一请求格式转换为OpenAI格式"""
        log("OpenAI Request:", json.dumps(request, indent=2))
        
        # 转换消息
        messages = []
        for msg in request.get("messages", []):
            role = msg.get("role")
            content = msg.get("content")
            
            if role in ["user", "assistant", "system"]:
                openai_msg = {"role": role}
                
                # 处理内容
                if isinstance(content, str):
                    openai_msg["content"] = content
                elif isinstance(content, list):
                    # 处理多模态内容
                    openai_msg["content"] = []
                    for item in content:
                        if item.get("type") == "text":
                            openai_msg["content"].append({
                                "type": "text",
                                "text": item.get("text", "")
                            })
                        elif item.get("type") == "image":
                            openai_msg["content"].append({
                                "type": "image_url",
                                "image_url": {
                                    "url": item.get("image_url", {}).get("url", ""),
                                    "detail": item.get("image_url", {}).get("detail", "auto")
                                }
                            })
                
                # 处理工具调用
                if msg.get("tool_calls"):
                    openai_msg["tool_calls"] = []
                    for tool_call in msg.get("tool_calls", []):
                        openai_msg["tool_calls"].append({
                            "id": tool_call.get("id", ""),
                            "type": tool_call.get("type", "function"),
                            "function": {
                                "name": tool_call.get("function", {}).get("name", ""),
                                "arguments": tool_call.get("function", {}).get("arguments", "{}")
                            }
                        })
                
                # 处理工具响应
                if role == "tool" and msg.get("tool_call_id"):
                    openai_msg["tool_call_id"] = msg.get("tool_call_id")
                
                messages.append(openai_msg)
        
        # 构建OpenAI请求
        openai_request = {
            "messages": messages,
            "model": request.get("model", ""),
            "stream": request.get("stream", False),
        }
        
        # 添加可选参数
        if "max_tokens" in request:
            openai_request["max_tokens"] = request["max_tokens"]
        
        if "temperature" in request:
            openai_request["temperature"] = request["temperature"]
        
        # 处理工具
        if request.get("tools"):
            openai_request["tools"] = []
            for tool in request.get("tools", []):
                if tool.get("type") == "function":
                    openai_request["tools"].append({
                        "type": "function",
                        "function": {
                            "name": tool.get("function", {}).get("name", ""),
                            "description": tool.get("function", {}).get("description", ""),
                            "parameters": tool.get("function", {}).get("parameters", {})
                        }
                    })
        
        # 处理工具选择
        if request.get("tool_choice"):
            tool_choice = request["tool_choice"]
            if isinstance(tool_choice, str):
                openai_request["tool_choice"] = tool_choice
            elif isinstance(tool_choice, dict) and tool_choice.get("type") == "function":
                openai_request["tool_choice"] = {
                    "type": "function",
                    "function": {
                        "name": tool_choice.get("function", {}).get("name", "")
                    }
                }
        
        return openai_request
    
    async def transform_request_out(self, request: Dict[str, Any]) -> UnifiedChatRequest:
        """将OpenAI格式转换为统一请求格式"""
        log("Transform OpenAI Request Out:", json.dumps(request, indent=2))
        
        # 转换消息
        messages = []
        for msg in request.get("messages", []):
            role = msg.get("role")
            content = msg.get("content")
            
            unified_msg = {
                "role": role,
                "content": content
            }
            
            # 处理工具调用
            if msg.get("tool_calls"):
                unified_msg["tool_calls"] = []
                for tool_call in msg.get("tool_calls", []):
                    unified_msg["tool_calls"].append({
                        "id": tool_call.get("id", ""),
                        "type": tool_call.get("type", "function"),
                        "function": {
                            "name": tool_call.get("function", {}).get("name", ""),
                            "arguments": tool_call.get("function", {}).get("arguments", "{}")
                        }
                    })
            
            # 处理工具响应
            if role == "tool" and msg.get("tool_call_id"):
                unified_msg["tool_call_id"] = msg.get("tool_call_id")
            
            messages.append(unified_msg)
        
        # 构建统一请求
        unified_request = {
            "messages": messages,
            "model": request.get("model", ""),
            "stream": request.get("stream", False),
        }
        
        # 添加可选参数
        if "max_tokens" in request:
            unified_request["max_tokens"] = request["max_tokens"]
        
        if "temperature" in request:
            unified_request["temperature"] = request["temperature"]
        
        # 处理工具
        if request.get("tools"):
            unified_request["tools"] = []
            for tool in request.get("tools", []):
                if tool.get("type") == "function":
                    unified_request["tools"].append({
                        "type": "function",
                        "function": {
                            "name": tool.get("function", {}).get("name", ""),
                            "description": tool.get("function", {}).get("description", ""),
                            "parameters": tool.get("function", {}).get("parameters", {})
                        }
                    })
        
        # 处理工具选择
        if request.get("tool_choice"):
            unified_request["tool_choice"] = request["tool_choice"]
        
        return UnifiedChatRequest(**unified_request)
    
    async def transform_response_in(self, response: httpx.Response) -> httpx.Response:
        """转换响应输入"""
        return response
    
    async def transform_response_out(self, response: httpx.Response) -> httpx.Response:
        """转换响应输出"""
        return response