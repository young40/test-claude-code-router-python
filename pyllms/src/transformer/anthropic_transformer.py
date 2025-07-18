import json
import httpx
import asyncio
import time
from typing import Dict, Any, List, Optional, Union

from ..types.transformer import Transformer, TransformerOptions
from ..types.llm import UnifiedChatRequest, UnifiedMessage, UnifiedTool, LLMProvider
from ..utils.log import log


class AnthropicTransformer(Transformer):
    """Anthropic transformer"""
    
    def __init__(self, options: Optional[TransformerOptions] = None):
        super().__init__(options)
        self.name = "Anthropic"
        self.end_point = "/v1/messages"
    
    async def transform_request_out(self, request: Dict[str, Any]) -> UnifiedChatRequest:
        """Transform Anthropic format to unified request format"""
        log("Anthropic Request:", json.dumps(request, indent=2))
        
        messages = []
        
        # Handle system message
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
        
        # Handle messages
        request_messages = json.loads(json.dumps(request.get("messages", [])))
        
        for msg in request_messages:
            if msg.get("role") in ["user", "assistant"]:
                unified_msg = {
                    "role": msg["role"],
                    "content": None
                }
                
                if isinstance(msg.get("content"), str):
                    messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
                elif isinstance(msg.get("content"), list):
                    if msg["role"] == "user":
                        # Handle tool results
                        tool_parts = [
                            part for part in msg["content"]
                            if part.get("type") == "tool_result" and part.get("tool_use_id")
                        ]
                        
                        if tool_parts:
                            for tool in tool_parts:
                                tool_message = {
                                    "role": "tool",
                                    "content": tool["content"] if isinstance(tool["content"], str) else json.dumps(tool["content"]),
                                    "tool_call_id": tool["tool_use_id"],
                                    "cache_control": tool.get("cache_control")
                                }
                                messages.append(tool_message)
                        
                        # Handle text parts
                        text_parts = [
                            part for part in msg["content"]
                            if part.get("type") == "text" and part.get("text")
                        ]
                        
                        if text_parts:
                            messages.append({
                                "role": "user",
                                "content": text_parts
                            })
                    elif msg["role"] == "assistant":
                        # Handle assistant message
                        assistant_message = {
                            "role": "assistant",
                            "content": None
                        }
                        
                        text_parts = [
                            part for part in msg["content"]
                            if part.get("type") == "text" and part.get("text")
                        ]
                        
                        if text_parts:
                            assistant_message["content"] = "\n".join(part["text"] for part in text_parts)
                        
                        # Handle tool calls
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
        
        # Build unified request
        result = UnifiedChatRequest(
            messages=messages,
            model=request.get("model", ""),
            max_tokens=request.get("max_tokens"),
            temperature=request.get("temperature"),
            stream=request.get("stream", False),
            tools=self._convert_anthropic_tools_to_unified(request["tools"]) if request.get("tools") else None,
            tool_choice=request.get("tool_choice")
        )
        
        return result
    
    async def transform_response_in(self, response: httpx.Response) -> httpx.Response:
        """Transform provider response to unified response format"""
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
    
    def _convert_anthropic_tools_to_unified(self, tools: List[Dict[str, Any]]) -> List[UnifiedTool]:
        """Convert Anthropic tools to unified format"""
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
    
    async def _convert_openai_stream_to_anthropic(self, response: httpx.Response) -> asyncio.StreamReader:
        """Convert OpenAI stream to Anthropic stream format"""
        # Create a StreamReader/StreamWriter pair for async streaming
        reader, writer = await asyncio.open_connection(
            host=None,
            port=None,
            pipe=asyncio.subprocess.PIPE
        )
        
        # Process the stream in a background task
        asyncio.create_task(self._process_stream(response, writer))
        
        return reader
    
    async def _process_stream(self, response: httpx.Response, writer: asyncio.StreamWriter):
        """Process the OpenAI stream and write Anthropic format to the writer"""
        try:
            encoder = self._get_encoder()
            message_id = f"msg_{int(time.time() * 1000)}"
            model = "unknown"
            has_started = False
            has_text_content_started = False
            has_finished = False
            tool_calls = {}
            tool_call_index_to_content_block_index = {}
            content_index = 0
            
            async for chunk in response.aiter_bytes():
                if has_finished:
                    break
                    
                chunk_str = chunk.decode('utf-8', errors='replace')
                lines = chunk_str.split('\n')
                
                for line in lines:
                    if has_finished:
                        break
                        
                    if not line.startswith('data: '):
                        continue
                        
                    data = line[6:]
                    if data == "[DONE]":
                        continue
                    
                    try:
                        chunk_data = json.loads(data)
                        log(f"Original Response: {json.dumps(chunk_data, indent=2)}")
                        
                        # Handle error responses
                        if chunk_data.get("error"):
                            error_message = {
                                "type": "error",
                                "message": {
                                    "type": "api_error",
                                    "message": json.dumps(chunk_data["error"])
                                }
                            }
                            writer.write(encoder[0](f"event: error\ndata: {json.dumps(error_message)}\n\n"))
                            await writer.drain()
                            continue
                        
                        # Record model information
                        if chunk_data.get("model"):
                            model = chunk_data["model"]
                        
                        # Handle message start
                        if not has_started and not has_finished:
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
                            writer.write(encoder[0](f"event: message_start\ndata: {json.dumps(message_start)}\n\n"))
                            await writer.drain()
                        
                        # Get the choice from the chunk
                        choice = chunk_data.get("choices", [{}])[0] if chunk_data.get("choices") else None
                        if not choice:
                            continue
                        
                        # Handle thinking content (if available)
                        if choice.get("delta", {}).get("thinking") and not has_finished:
                            thinking_data = choice["delta"]["thinking"]
                            if "signature" in thinking_data:
                                # Handle thinking signature
                                thinking_signature = {
                                    "type": "content_block_delta",
                                    "index": content_index,
                                    "delta": {
                                        "type": "signature_delta",
                                        "signature": thinking_data["signature"]
                                    }
                                }
                                writer.write(encoder[0](f"event: content_block_delta\ndata: {json.dumps(thinking_signature)}\n\n"))
                                await writer.drain()
                                
                                # End the thinking content block
                                content_block_stop = {
                                    "type": "content_block_stop",
                                    "index": content_index
                                }
                                writer.write(encoder[0](f"event: content_block_stop\ndata: {json.dumps(content_block_stop)}\n\n"))
                                await writer.drain()
                                content_index += 1
                            elif thinking_data.get("content"):
                                # Handle thinking content
                                thinking_chunk = {
                                    "type": "content_block_delta",
                                    "index": content_index,
                                    "delta": {
                                        "type": "thinking_delta",
                                        "thinking": thinking_data["content"]
                                    }
                                }
                                writer.write(encoder[0](f"event: content_block_delta\ndata: {json.dumps(thinking_chunk)}\n\n"))
                                await writer.drain()
                        
                        # Handle text content
                        if choice.get("delta", {}).get("content") and not has_finished:
                            content = choice["delta"]["content"]
                            
                            # Start a new text content block if needed
                            if not has_text_content_started and not has_finished:
                                has_text_content_started = True
                                content_block_start = {
                                    "type": "content_block_start",
                                    "index": content_index,
                                    "content_block": {
                                        "type": "text",
                                        "text": ""
                                    }
                                }
                                writer.write(encoder[0](f"event: content_block_start\ndata: {json.dumps(content_block_start)}\n\n"))
                                await writer.drain()
                            
                            # Send the text delta
                            text_delta = {
                                "type": "content_block_delta",
                                "index": content_index,
                                "delta": {
                                    "type": "text_delta",
                                    "text": content
                                }
                            }
                            writer.write(encoder[0](f"event: content_block_delta\ndata: {json.dumps(text_delta)}\n\n"))
                            await writer.drain()
                        
                        # Handle tool calls
                        if choice.get("delta", {}).get("tool_calls") and not has_finished:
                            for tool_call in choice["delta"]["tool_calls"]:
                                tool_call_index = tool_call.get("index", 0)
                                
                                # Check if this is a new tool call
                                if tool_call_index not in tool_calls:
                                    # End previous content block if needed
                                    if has_text_content_started or tool_calls:
                                        content_block_stop = {
                                            "type": "content_block_stop",
                                            "index": content_index
                                        }
                                        writer.write(encoder[0](f"event: content_block_stop\ndata: {json.dumps(content_block_stop)}\n\n"))
                                        await writer.drain()
                                        content_index += 1
                                    
                                    # Create a new tool call
                                    tool_call_id = tool_call.get("id") or f"call_{int(time.time() * 1000)}_{tool_call_index}"
                                    tool_call_name = tool_call.get("function", {}).get("name") or f"tool_{tool_call_index}"
                                    
                                    # Start a new tool use content block
                                    content_block_start = {
                                        "type": "content_block_start",
                                        "index": content_index,
                                        "content_block": {
                                            "type": "tool_use",
                                            "id": tool_call_id,
                                            "name": tool_call_name,
                                            "input": {}
                                        }
                                    }
                                    writer.write(encoder[0](f"event: content_block_start\ndata: {json.dumps(content_block_start)}\n\n"))
                                    await writer.drain()
                                    
                                    # Store the tool call information
                                    tool_calls[tool_call_index] = {
                                        "id": tool_call_id,
                                        "name": tool_call_name,
                                        "arguments": "",
                                        "content_block_index": content_index
                                    }
                                    tool_call_index_to_content_block_index[tool_call_index] = content_index
                                
                                # Update existing tool call with new information
                                elif tool_call.get("id") and tool_call.get("function", {}).get("name"):
                                    existing_tool_call = tool_calls[tool_call_index]
                                    if existing_tool_call["id"].startswith("call_") and existing_tool_call["name"].startswith("tool_"):
                                        existing_tool_call["id"] = tool_call["id"]
                                        existing_tool_call["name"] = tool_call["function"]["name"]
                                
                                # Handle tool call arguments
                                if tool_call.get("function", {}).get("arguments"):
                                    arguments = tool_call["function"]["arguments"]
                                    current_tool_call = tool_calls.get(tool_call_index)
                                    
                                    if current_tool_call:
                                        current_tool_call["arguments"] += arguments
                                        
                                        # Send the argument delta
                                        try:
                                            input_json_delta = {
                                                "type": "content_block_delta",
                                                "index": tool_call_index_to_content_block_index[tool_call_index],
                                                "delta": {
                                                    "type": "input_json_delta",
                                                    "partial_json": arguments
                                                }
                                            }
                                            writer.write(encoder[0](f"event: content_block_delta\ndata: {json.dumps(input_json_delta)}\n\n"))
                                            await writer.drain()
                                        except Exception as e:
                                            log(f"Error sending tool call arguments: {e}")
                                            # Try with sanitized arguments
                                            try:
                                                fixed_argument = arguments.replace("\\", "\\\\").replace('"', '\\"')
                                                fixed_delta = {
                                                    "type": "content_block_delta",
                                                    "index": tool_call_index_to_content_block_index[tool_call_index],
                                                    "delta": {
                                                        "type": "input_json_delta",
                                                        "partial_json": fixed_argument
                                                    }
                                                }
                                                writer.write(encoder[0](f"event: content_block_delta\ndata: {json.dumps(fixed_delta)}\n\n"))
                                                await writer.drain()
                                            except Exception as fix_error:
                                                log(f"Error sending fixed tool call arguments: {fix_error}")
                        
                        # Handle finish reason
                        if choice.get("finish_reason") and not has_finished:
                            has_finished = True
                            
                            # End the current content block
                            if has_text_content_started or tool_calls:
                                content_block_stop = {
                                    "type": "content_block_stop",
                                    "index": content_index
                                }
                                writer.write(encoder[0](f"event: content_block_stop\ndata: {json.dumps(content_block_stop)}\n\n"))
                                await writer.drain()
                            
                            # Map the finish reason
                            stop_reason_mapping = {
                                "stop": "end_turn",
                                "length": "max_tokens",
                                "tool_calls": "tool_use",
                                "content_filter": "stop_sequence"
                            }
                            anthropic_stop_reason = stop_reason_mapping.get(choice["finish_reason"], "end_turn")
                            
                            # Send the message delta
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
                            writer.write(encoder[0](f"event: message_delta\ndata: {json.dumps(message_delta)}\n\n"))
                            await writer.drain()
                            
                            # Send the message stop
                            message_stop = {
                                "type": "message_stop"
                            }
                            writer.write(encoder[0](f"event: message_stop\ndata: {json.dumps(message_stop)}\n\n"))
                            await writer.drain()
                            break
                    
                    except json.JSONDecodeError as e:
                        log(f"Error parsing JSON: {e} - Data: {data}")
                    except Exception as e:
                        log(f"Error processing stream: {e}")
        
        except Exception as e:
            log(f"Stream processing error: {e}")
        finally:
            # Close the writer when done
            writer.close()
            await writer.wait_closed()
    
    def _convert_openai_response_to_anthropic(self, openai_response: Dict[str, Any]) -> Dict[str, Any]:
        """Convert OpenAI response to Anthropic response format"""
        log("Original OpenAI response:", json.dumps(openai_response, indent=2))
        
        choice = openai_response.get("choices", [{}])[0]
        if not choice:
            raise ValueError("No choices found in OpenAI response")
        
        content = []
        
        # Handle text content
        if choice.get("message", {}).get("content"):
            content.append({
                "type": "text",
                "text": choice["message"]["content"]
            })
        
        # Handle tool calls
        if choice.get("message", {}).get("tool_calls"):
            for tool_call in choice["message"]["tool_calls"]:
                try:
                    arguments_str = tool_call.get("function", {}).get("arguments", "{}")
                    
                    if isinstance(arguments_str, object):
                        parsed_input = arguments_str
                    elif isinstance(arguments_str, str):
                        parsed_input = json.loads(arguments_str)
                    else:
                        parsed_input = {}
                except json.JSONDecodeError:
                    parsed_input = {"text": arguments_str}
                
                content.append({
                    "type": "tool_use",
                    "id": tool_call.get("id", ""),
                    "name": tool_call.get("function", {}).get("name", ""),
                    "input": parsed_input
                })
        
        # Map stop reason
        stop_reason_mapping = {
            "stop": "end_turn",
            "length": "max_tokens",
            "tool_calls": "tool_use",
            "content_filter": "stop_sequence"
        }
        
        stop_reason = stop_reason_mapping.get(choice.get("finish_reason"), "end_turn")
        
        # Build Anthropic response
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
        """Get text encoder"""
        import codecs
        return codecs.getencoder('utf-8')