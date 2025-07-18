import json
import time
from typing import Dict, Any, Optional
import httpx

from ..types.transformer import Transformer, TransformerOptions
from ..types.llm import UnifiedChatRequest, LLMProvider
from ..utils.log import log


class DeepseekTransformer(Transformer):
    """DeepSeek transformer"""
    
    def __init__(self, options: Optional[TransformerOptions] = None):
        super().__init__(options)
        self.name = "deepseek"
    
    async def transform_request_in(
        self, 
        request: UnifiedChatRequest, 
        provider: LLMProvider
    ) -> UnifiedChatRequest:
        """Transform request input, limit max tokens to DeepSeek's maximum"""
        if hasattr(request, 'max_tokens') and request.max_tokens and request.max_tokens > 8192:
            request.max_tokens = 8192  # DeepSeek has a max token limit of 8192
        return request
    
    async def transform_response_out(self, response: httpx.Response) -> httpx.Response:
        """Transform response output, handle reasoning content"""
        content_type = response.headers.get("Content-Type", "")
        
        if "application/json" in content_type:
            # Handle non-streaming response
            json_response = await response.json()
            return httpx.Response(
                status_code=response.status_code,
                headers=response.headers,
                json=json_response
            )
        elif "stream" in content_type:
            # Handle streaming response
            if not hasattr(response, 'aiter_bytes'):
                return response
            
            reasoning_content = ""
            is_reasoning_complete = False
            
            async def stream_generator():
                nonlocal reasoning_content, is_reasoning_complete
                
                async for chunk in response.aiter_bytes():
                    chunk_str = chunk.decode('utf-8')
                    lines = chunk_str.split('\n')
                    
                    for line in lines:
                        if line.startswith("data: ") and line.strip() != "data: [DONE]":
                            try:
                                data = json.loads(line[6:])
                                
                                # Extract reasoning content
                                if data.get("choices", [{}])[0].get("delta", {}).get("reasoning_content"):
                                    reasoning_content += data["choices"][0]["delta"]["reasoning_content"]
                                    
                                    # Create thinking chunk
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
                                    
                                    # Remove original reasoning content
                                    if "reasoning_content" in thinking_chunk["choices"][0]["delta"]:
                                        del thinking_chunk["choices"][0]["delta"]["reasoning_content"]
                                    
                                    thinking_line = f"data: {json.dumps(thinking_chunk)}\n\n"
                                    yield thinking_line.encode('utf-8')
                                    continue
                                
                                # Check if reasoning is complete
                                if (data.get("choices", [{}])[0].get("delta", {}).get("content") and 
                                    reasoning_content and not is_reasoning_complete):
                                    is_reasoning_complete = True
                                    signature = str(int(time.time() * 1000))
                                    
                                    # Create complete thinking block
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
                                
                                # Clean reasoning content
                                if data.get("choices", [{}])[0].get("delta", {}).get("reasoning_content"):
                                    del data["choices"][0]["delta"]["reasoning_content"]
                                
                                # Send modified chunk
                                if (data.get("choices", [{}])[0].get("delta") and 
                                    len(data["choices"][0]["delta"]) > 0):
                                    if is_reasoning_complete:
                                        data["choices"][0]["index"] = data["choices"][0].get("index", 0) + 1
                                    
                                    modified_line = f"data: {json.dumps(data)}\n\n"
                                    yield modified_line.encode('utf-8')
                                    
                            except json.JSONDecodeError:
                                # JSON parsing failed, pass through original line
                                yield (line + "\n").encode('utf-8')
                        else:
                            # Pass through non-data lines
                            yield (line + "\n").encode('utf-8')
            
            # Return a streaming response
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