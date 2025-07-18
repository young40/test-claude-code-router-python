import json
import uuid
from typing import Dict, Any, Optional, List
import httpx

from ..types.transformer import Transformer, TransformerOptions
from ..types.llm import UnifiedChatRequest, MessageContent, TextContent
from ..utils.log import log


class GroqTransformer(Transformer):
    """Groq转换器"""
    
    def __init__(self, options: Optional[TransformerOptions] = None):
        super().__init__(options)
        self.name = "groq"
    
    async def transform_request_in(
        self, 
        request: UnifiedChatRequest, 
        provider=None
    ) -> UnifiedChatRequest:
        """转换请求输入，清理缓存控制字段"""
        
        # 清理消息中的缓存控制字段
        for msg in request.messages:
            if isinstance(msg.content, list):
                for item in msg.content:
                    if hasattr(item, 'cache_control'):
                        delattr(item, 'cache_control')
            elif hasattr(msg, 'cache_control'):
                delattr(msg, 'cache_control')
        
        # 清理工具中的$schema字段
        if hasattr(request, 'tools') and request.tools:
            for tool in request.tools:
                if hasattr(tool, 'function') and hasattr(tool.function, 'parameters'):
                    if isinstance(tool.function.parameters, dict) and '$schema' in tool.function.parameters:
                        del tool.function.parameters['$schema']
        
        return request
    
    async def transform_response_out(self, response: httpx.Response) -> httpx.Response:
        """转换响应输出，处理流式响应中的工具调用"""
        content_type = response.headers.get("Content-Type", "")
        
        if "application/json" in content_type:
            # 处理非流式响应
            json_response = await response.json()
            return httpx.Response(
                status_code=response.status_code,
                headers=response.headers,
                json=json_response
            )
        elif "stream" in content_type:
            # 处理流式响应
            if not hasattr(response, 'aiter_bytes'):
                return response
            
            has_text_content = False
            reasoning_content = ""
            is_reasoning_complete = False
            buffer = ""  # 用于缓冲不完整的数据
            
            async def stream_generator():
                nonlocal has_text_content, reasoning_content, is_reasoning_complete, buffer
                
                def process_line(line: str):
                    nonlocal has_text_content, reasoning_content, is_reasoning_complete
                    
                    if line.startswith("data: ") and line.strip() != "data: [DONE]":
                        json_str = line[6:]
                        try:
                            data = json.loads(json_str)
                            
                            if data.get("error"):
                                raise Exception(json.dumps(data))
                            
                            # 检查是否有文本内容
                            if (data.get("choices", [{}])[0].get("delta", {}).get("content") and 
                                not has_text_content):
                                has_text_content = True
                            
                            # 处理工具调用，为每个工具调用生成UUID
                            if data.get("choices", [{}])[0].get("delta", {}).get("tool_calls"):
                                for tool in data["choices"][0]["delta"]["tool_calls"]:
                                    tool["id"] = f"call_{str(uuid.uuid4())}"
                            
                            # 如果有工具调用且已有文本内容，调整索引
                            if (data.get("choices", [{}])[0].get("delta", {}).get("tool_calls") and 
                                has_text_content):
                                current_index = data["choices"][0].get("index", 0)
                                data["choices"][0]["index"] = current_index + 1
                            
                            modified_line = f"data: {json.dumps(data)}\n\n"
                            return modified_line.encode('utf-8')
                            
                        except json.JSONDecodeError:
                            # JSON解析失败，传递原始行
                            return (line + "\n").encode('utf-8')
                    else:
                        # 传递非数据行
                        return (line + "\n").encode('utf-8')
                
                async for chunk in response.aiter_bytes():
                    if not chunk:
                        continue
                    
                    try:
                        chunk_str = chunk.decode('utf-8')
                    except UnicodeDecodeError:
                        log("Failed to decode chunk, skipping")
                        continue
                    
                    if not chunk_str:
                        continue
                    
                    buffer += chunk_str
                    
                    # 防止缓冲区过大
                    if len(buffer) > 1000000:  # 1MB限制
                        log("Buffer size exceeds limit, processing partial data")
                        lines = buffer.split("\n")
                        buffer = lines.pop() or ""
                        
                        for line in lines:
                            if line.strip():
                                try:
                                    yield process_line(line)
                                except Exception as e:
                                    log(f"Error processing line: {line}, error: {e}")
                                    yield (line + "\n").encode('utf-8')
                        continue
                    
                    # 处理缓冲区中完整的数据行
                    lines = buffer.split("\n")
                    buffer = lines.pop() or ""  # 最后一行可能不完整
                    
                    for line in lines:
                        if not line.strip():
                            continue
                        
                        try:
                            yield process_line(line)
                        except Exception as e:
                            log(f"Error processing line: {line}, error: {e}")
                            yield (line + "\n").encode('utf-8')
                
                # 处理缓冲区中剩余的数据
                if buffer.strip():
                    try:
                        yield process_line(buffer.strip())
                    except Exception as e:
                        log(f"Error processing final buffer: {buffer}, error: {e}")
                        yield (buffer + "\n").encode('utf-8')
            
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