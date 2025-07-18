import json
import httpx
import asyncio
import time
from typing import Dict, Any, List, Optional, Union

from ..types.transformer import Transformer, TransformerOptions
from ..types.llm import UnifiedChatRequest, UnifiedMessage, UnifiedTool, LLMProvider
from ..utils.log import log


class AnthropicTransformer(Transformer):
    """Anthropic转换器"""
    
    def __init__(self, options: Optional[TransformerOptions] = None):
        super().__init__(options)
        self.name = "Anthropic"
        self.end_point = "/v1/messages"
    
    async def transform_request_out(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """将Anthropic格式转换为统一请求格式"""
        log("Anthropic Request:", json.dumps(request, indent=2))
        
        messages = []
        
        # 处理系统消息
        if "system" in request:
            if isinstance(request["system"], str):
                messages.append({
                    "role": "system",
                    "content": request["system"]
                })
            elif isinstance(request["system"], list):
                text_parts = [
                    {"type": "text", "text": item["text"], "cache_control": item.get("cache_control")}
                    for item in request["system"]
                    if item.get("type") == "text" and item.get("text")
                ]
                messages.append({
                    "role": "system",
                    "content": text_parts
                })
        
        # 处理消息
        request_messages = request.get("messages", [])
        if isinstance(request_messages, list):
            for msg in request_messages:
                if msg.get("role") in ["user", "assistant"]:
                    if msg.get("role") == "user":
                        # 处理用户消息
                        if isinstance(msg.get("content"), str):
                            messages.append({
                                "role": "user",
                                "content": msg["content"]
                            })
                        elif isinstance(msg.get("content"), list):
                            # 处理工具结果
                            tool_parts = [
                                part for part in msg["content"]
                                if part.get("type") == "tool_result" and part.get("tool_use_id")
                            ]
                            
                            for tool in tool_parts:
                                tool_message = {
                                    "role": "tool",
                                    "content": tool["content"] if isinstance(tool["content"], str) else json.dumps(tool["content"]),
                                    "tool_call_id": tool["tool_use_id"],
                                    "cache_control": tool.get("cache_control")
                                }
                                messages.append(tool_message)
                            
                            # 处理文本部分
                            text_parts = [
                                part for part in msg["content"]
                                if part.get("type") == "text" and part.get("text")
                            ]
                            
                            if text_parts:
                                messages.append({
                                    "role": "user",
                                    "content": text_parts
                                })
                    
                    elif msg.get("role") == "assistant":
                        # 处理助手消息
                        assistant_message = {
                            "role": "assistant",
                            "content": None
                        }
                        
                        if isinstance(msg.get("content"), str):
                            assistant_message["content"] = msg["content"]
                        elif isinstance(msg.get("content"), list):
                            # 处理文本部分
                            text_parts = [
                                part for part in msg["content"]
                                if part.get("type") == "text" and part.get("text")
                            ]
                            
                            if text_parts:
                                assistant_message["content"] = "\n".join(part["text"] for part in text_parts)
                            
                            # 处理工具调用
                            tool_call_parts = [
                                part for part in msg["content"]
                                if part.get("type") == "tool_use" and part.get("id")
                            ]
                            
                            if tool_call_parts:
                                assistant_message["tool_calls"] = [
                                    {
                                        "id": tool["id"],
                                        "type": "function",
                                        "function": {
                                            "name": tool["name"],
                                            "arguments": json.dumps(tool.get("input", {}))
                                        }
                                    }
                                    for tool in tool_call_parts
                                ]
                        
                        messages.append(assistant_message)
        
        # 构建统一请求
        result = {
            "messages": messages,
            "model": request.get("model", ""),
            "max_tokens": request.get("max_tokens"),
            "temperature": request.get("temperature"),
            "stream": request.get("stream", False)
        }
        
        # 处理工具
        if request.get("tools"):
            result["tools"] = self._convert_anthropic_tools_to_unified(request["tools"])
        
        # 处理工具选择
        if request.get("tool_choice"):
            result["tool_choice"] = request["tool_choice"]
        
        return result
    
    async def transform_response_in(self, response: httpx.Response) -> httpx.Response:
        """转换响应输入"""
        is_stream = "text/event-stream" in response.headers.get("content-type", "")
        
        if is_stream:
            if not response.is_stream_consumed:
                converted_stream = await self._convert_openai_stream_to_anthropic(response)
                return httpx.Response(
                    status_code=response.status_code,
                    headers={
                        "Content-Type": "text/event-stream",
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive"
                    },
                    stream=converted_stream
                )
            return response
        else:
            data = await response.json()
            anthropic_response = self._convert_openai_response_to_anthropic(data)
            return httpx.Response(
                status_code=response.status_code,
                headers={"Content-Type": "application/json"},
                json=anthropic_response
            )
    
    def _convert_anthropic_tools_to_unified(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """将Anthropic工具转换为统一格式"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {})
                }
            }
            for tool in tools
        ]
    
    async def _convert_openai_stream_to_anthropic(self, response: httpx.Response) -> bytes:
        """将OpenAI流转换为Anthropic流"""
        # 这里是一个简化的实现，实际情况可能需要更复杂的处理
        # 在实际应用中，需要逐行解析OpenAI的SSE流并转换为Anthropic格式
        
        async def stream_generator():
            encoder = self._get_encoder()
            message_id = f"msg_{int(time.time() * 1000)}"
            model = "unknown"
            has_started = False
            
            async for chunk in response.aiter_bytes():
                chunk_str = chunk.decode('utf-8')
                lines = chunk_str.split('\n')
                
                for line in lines:
                    if line.startswith('data: '):
                        data = line[6:]
                        if data == "[DONE]":
                            continue
                        
                        try:
                            chunk_data = json.loads(data)
                            
                            # 记录模型信息
                            if chunk_data.get("model"):
                                model = chunk_data["model"]
                            
                            # 处理开始消息
                            if not has_started:
                                has_started = True
                                message_start = {
                                    "type": "message_start",
                                    "message": {
                                        "id": message_id,
                                        "type": "message",
                                        "role": "assistant",
                                        "content": [],
                                        "model": model,
                                        "stop_reason": None,
                                        "stop_sequence": None,
                                        "usage": {"input_tokens": 1, "output_tokens": 1}
                                    }
                                }
                                yield encoder.encode(f"event: message_start\ndata: {json.dumps(message_start)}\n\n")
                            
                            # 处理内容块
                            choice = chunk_data.get("choices", [{}])[0]
                            if choice and choice.get("delta", {}).get("content"):
                                content = choice["delta"]["content"]
                                content_block = {
                                    "type": "content_block_delta",
                                    "index": 0,
                                    "delta": {
                                        "type": "text_delta",
                                        "text": content
                                    }
                                }
                                yield encoder.encode(f"event: content_block_delta\ndata: {json.dumps(content_block)}\n\n")
                            
                            # 处理结束消息
                            if choice and choice.get("finish_reason"):
                                stop_reason_mapping = {
                                    "stop": "end_turn",
                                    "length": "max_tokens",
                                    "tool_calls": "tool_use",
                                    "content_filter": "stop_sequence"
                                }
                                
                                anthropic_stop_reason = stop_reason_mapping.get(choice["finish_reason"], "end_turn")
                                
                                message_delta = {
                                    "type": "message_delta",
                                    "delta": {
                                        "stop_reason": anthropic_stop_reason,
                                        "stop_sequence": None
                                    },
                                    "usage": {
                                        "input_tokens": chunk_data.get("usage", {}).get("prompt_tokens", 0),
                                        "output_tokens": chunk_data.get("usage", {}).get("completion_tokens", 0)
                                    }
                                }
                                yield encoder.encode(f"event: message_delta\ndata: {json.dumps(message_delta)}\n\n")
                                
                                message_stop = {
                                    "type": "message_stop"
                                }
                                yield encoder.encode(f"event: message_stop\ndata: {json.dumps(message_stop)}\n\n")
                        
                        except json.JSONDecodeError:
                            log(f"Error parsing JSON: {data}")
        
        return b''.join([chunk async for chunk in stream_generator()])
    
    def _convert_openai_response_to_anthropic(self, openai_response: Dict[str, Any]) -> Dict[str, Any]:
        """将OpenAI响应转换为Anthropic响应"""
        log("Original OpenAI response:", json.dumps(openai_response, indent=2))
        
        choice = openai_response.get("choices", [{}])[0]
        if not choice:
            raise ValueError("No choices found in OpenAI response")
        
        content = []
        
        # 处理文本内容
        if choice.get("message", {}).get("content"):
            content.append({
                "type": "text",
                "text": choice["message"]["content"]
            })
        
        # 处理工具调用
        if choice.get("message", {}).get("tool_calls"):
            for tool_call in choice["message"]["tool_calls"]:
                try:
                    arguments_str = tool_call.get("function", {}).get("arguments", "{}")
                    parsed_input = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
                except json.JSONDecodeError:
                    parsed_input = {"text": arguments_str}
                
                content.append({
                    "type": "tool_use",
                    "id": tool_call.get("id", ""),
                    "name": tool_call.get("function", {}).get("name", ""),
                    "input": parsed_input
                })
        
        # 映射停止原因
        stop_reason_mapping = {
            "stop": "end_turn",
            "length": "max_tokens",
            "tool_calls": "tool_use",
            "content_filter": "stop_sequence"
        }
        
        stop_reason = stop_reason_mapping.get(choice.get("finish_reason"), "end_turn")
        
        # 构建Anthropic响应
        result = {
            "id": openai_response.get("id", ""),
            "type": "message",
            "role": "assistant",
            "model": openai_response.get("model", ""),
            "content": content,
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {
                "input_tokens": openai_response.get("usage", {}).get("prompt_tokens", 0),
                "output_tokens": openai_response.get("usage", {}).get("completion_tokens", 0)
            }
        }
        
        log("Conversion complete, final Anthropic response:", json.dumps(result, indent=2))
        return result
    
    def _get_encoder(self):
        """获取文本编码器"""
        import codecs
        return codecs.getencoder('utf-8')