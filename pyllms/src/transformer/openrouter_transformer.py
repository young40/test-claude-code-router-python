import json
import time
from typing import Dict, Any, Optional
import httpx

from ..types.transformer import Transformer, TransformerOptions
from ..types.llm import UnifiedChatRequest, MessageContent, TextContent
from ..utils.log import log


class OpenrouterTransformer(Transformer):
    """OpenRouter transformer"""
    
    def __init__(self, options: Optional[TransformerOptions] = None):
        super().__init__(options)
        self.name = "openrouter"
    
    async def transform_request_in(
        self, 
        request: UnifiedChatRequest, 
        provider=None
    ) -> UnifiedChatRequest:
        """Transform request input, clean cache control fields for non-Claude models"""
        
        # If not a Claude model, clean cache control fields
        if not ('claude' in request.model.lower()):
            for msg in request.messages:
                if isinstance(msg.content, list):
                    for item in msg.content:
                        if hasattr(item, 'cache_control'):
                            delattr(item, 'cache_control')
                elif hasattr(msg, 'cache_control'):
                    delattr(msg, 'cache_control')
        
        return request
    
    async def transform_response_out(self, response: httpx.Response) -> httpx.Response:
        """Transform response output, handle reasoning content and tool calls"""
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
            
            has_text_content = False
            reasoning_content = ""
            is_reasoning_complete = False
            buffer = ""  # Buffer for incomplete data
            
            async def stream_generator():
                nonlocal has_text_content, reasoning_content, is_reasoning_complete, buffer
                
                def process_line(line: str):
                    nonlocal has_text_content, reasoning_content, is_reasoning_complete
                    
                    if line.startswith("data: ") and line.strip() != "data: [DONE]":
                        json_str = line[6:]
                        try:
                            data = json.loads(json_str)
                            
                            # Check if there's text content
                            if (data.get("choices", [{}])[0].get("delta", {}).get("content") and 
                                not has_text_content):
                                has_text_content = True
                            
                            # Extract reasoning content
                            if data.get("choices", [{}])[0].get("delta", {}).get("reasoning"):
                                reasoning_content += data["choices"][0]["delta"]["reasoning"]
                                
                                # Create thinking chunk
                                thinking_chunk = {
                                    **data,
                                    "choices": [{
                                        **data["choices"][0],
                                        "delta": {
                                            **data["choices"][0]["delta"],
                                            "thinking": {
                                                "content": data["choices"][0]["delta"]["reasoning"]
                                            }
                                        }
                                    }]
                                }
                                
                                # Remove original reasoning field
                                if "reasoning" in thinking_chunk["choices"][0]["delta"]:
                                    del thinking_chunk["choices"][0]["delta"]["reasoning"]
                                
                                thinking_line = f"data: {json.dumps(thinking_chunk)}\n\n"
                                return thinking_line.encode('utf-8')
                            
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
                                
                                if "reasoning" in thinking_chunk["choices"][0]["delta"]:
                                    del thinking_chunk["choices"][0]["delta"]["reasoning"]
                                
                                thinking_line = f"data: {json.dumps(thinking_chunk)}\n\n"
                                return thinking_line.encode('utf-8')
                            
                            # Clean reasoning field
                            if data.get("choices", [{}])[0].get("delta", {}).get("reasoning"):
                                del data["choices"][0]["delta"]["reasoning"]
                            
                            # If there are tool calls and text content, adjust index
                            if (data.get("choices", [{}])[0].get("delta", {}).get("tool_calls") and 
                                has_text_content):
                                if isinstance(data["choices"][0].get("index"), int):
                                    data["choices"][0]["index"] += 1
                                else:
                                    data["choices"][0]["index"] = 1
                            
                            modified_line = f"data: {json.dumps(data)}\n\n"
                            return modified_line.encode('utf-8')
                            
                        except json.JSONDecodeError:
                            # JSON parsing failed, pass through original line
                            return (line + "\n").encode('utf-8')
                    else:
                        # Pass through non-data lines
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
                    
                    # Prevent buffer from getting too large
                    if len(buffer) > 1000000:  # 1MB limit
                        log("Buffer size exceeds limit, processing partial data")
                        lines = buffer.split("\n")
                        buffer = lines.pop() or ""
                        
                        for line in lines:
                            if line.strip():
                                try:
                                    result = process_line(line)
                                    if result:
                                        yield result
                                except Exception as e:
                                    log(f"Error processing line: {line}, error: {e}")
                                    yield (line + "\n").encode('utf-8')
                        continue
                    
                    # Process complete data lines in buffer
                    lines = buffer.split("\n")
                    buffer = lines.pop() or ""  # Last line may be incomplete
                    
                    for line in lines:
                        if not line.strip():
                            continue
                        
                        try:
                            result = process_line(line)
                            if result:
                                yield result
                        except Exception as e:
                            log(f"Error processing line: {line}, error: {e}")
                            yield (line + "\n").encode('utf-8')
                
                # Process remaining data in buffer
                if buffer.strip():
                    try:
                        result = process_line(buffer.strip())
                        if result:
                            yield result
                    except Exception as e:
                        log(f"Error processing final buffer: {buffer}, error: {e}")
                        yield (buffer + "\n").encode('utf-8')
            
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