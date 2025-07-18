import json
import asyncio
from typing import Dict, Any, Optional
import httpx

from ..types.transformer import Transformer, TransformerOptions
from ..types.llm import UnifiedChatRequest, LLMProvider
from ..utils.log import log


class DeepseekTransformer(Transformer):
    """DeepSeek转换器"""
    
    def __init__(self, options: Optional[TransformerOptions] = None):
        super().__init__(options)
        self.name = "deepseek"
    
    async def transform_request_in(
        self, 
        request: UnifiedChatRequest, 
        provider: LLMProvider
    ) -> UnifiedChatRequest:
        """转换请求输入，限制最大token数"""
        if hasattr(request, 'max_tokens') and request.max_tokens and request.max_tokens > 8192:
            request.max_tokens = 8192  # DeepSeek has a max token limit of 8192
        return request
    
    async def transform_response_out(self, response: httpx.Response) -> httpx.Response:
        """转换响应输出，处理推理内容"""
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
            
            reasoning_content = ""
            is_reasoning_complete = False
            
            async def stream_generator():
                async for chunk in response.aiter_bytes():
                    chunk_str = chunk.decode('utf-8')
                    lines = chunk_str.split('\n')
                    
                    for line in lines:
                        if line.startswith("data: ") and line.strip() != "data: [DONE]":
                            try:
                                data = json.loads(line[6:])
                                
                                # 提取推理内容
                                if (data.get("choices", [{}])[0].get("delta", {}).get("reasoning_content")):
                                    nonlocal reasoning_content
                                    reasoning_content += data["choices"][0]["delta"]["reasoning_content"]
                                    
                                    # 创建思考块
                                    thinking_chunk = {
                                        **data,
                                        "choices": [{
                                            **data["choices"][0],
                                            "delta": {
                                                **data["choices"][0]["delta"],
                                                "thinking": {
                                                    "content": data["choices"][0]["delta"]["reasoning_content"]
                                                }
                                            }
                                        }]
                                    }
                                    
                                    # 删除原始推理内容
                                    if "reasoning_content" in thinking_chunk["choices"][0]["delta"]:
                                        del thinking_chunk["choices"][0]["delta"]["reasoning_content"]
                                    
                                    thinking_line = f"data: {json.dumps(thinking_chunk)}\n\n"
                                    yield thinking_line.encode('utf-8')
                                    continue
                                
                                # 检查推理是否完成
                                if (data.get("choices", [{}])[0].get("delta", {}).get("content") and 
                                    reasoning_content and not is_reasoning_complete):
                                    is_reasoning_complete = True
                                    signature = str(int(asyncio.get_event_loop().time() * 1000))
                                    
                                    # 创建完整的思考块
                                    thinking_chunk = {
                                        **data,
                                        "choices": [{
                                            **data["choices"][0],
                                            "delta": {
                                                **data["choices"][0]["delta"],
                                                "content": None,
                                                "thinking": {
                                                    "content": reasoning_content,
                                                    "signature": signature
                                                }
                                            }
                                        }]
                                    }
                                    
                                    if "reasoning_content" in thinking_chunk["choices"][0]["delta"]:
                                        del thinking_chunk["choices"][0]["delta"]["reasoning_content"]
                                    
                                    thinking_line = f"data: {json.dumps(thinking_chunk)}\n\n"
                                    yield thinking_line.encode('utf-8')
                                
                                # 清理推理内容
                                if data.get("choices", [{}])[0].get("delta", {}).get("reasoning_content"):
                                    del data["choices"][0]["delta"]["reasoning_content"]
                                
                                # 发送修改后的块
                                if (data.get("choices", [{}])[0].get("delta") and 
                                    len(data["choices"][0]["delta"]) > 0):
                                    if is_reasoning_complete:
                                        data["choices"][0]["index"] = data["choices"][0].get("index", 0) + 1
                                    
                                    modified_line = f"data: {json.dumps(data)}\n\n"
                                    yield modified_line.encode('utf-8')
                                    
                            except json.JSONDecodeError:
                                # JSON解析失败，传递原始行
                                yield (line + "\n").encode('utf-8')
                        else:
                            # 传递非数据行
                            yield (line + "\n").encode('utf-8')
            
            # Create a new response with the modified stream
            class StreamingResponse:
                def __init__(self, status_code, headers, stream_func):
                    self.status_code = status_code
                    self.headers = headers
                    self._stream_func = stream_func
                
                async def aiter_bytes(self):
                    async for chunk in self._stream_func():
                        yield chunk
                
                def json(self):
                    raise NotImplementedError("Cannot call json() on streaming response")
            
            return StreamingResponse(
                status_code=response.status_code,
                headers={
                    "Content-Type": content_type,
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive"
                },
                stream_func=stream_generator
            )
        
        return response