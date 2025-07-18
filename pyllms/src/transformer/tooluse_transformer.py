import json
from typing import Dict, Any, Optional, Union
import httpx
from fastapi.responses import StreamingResponse

from ..types.transformer import Transformer, TransformerOptions, TransformRequestResult
from ..types.llm import UnifiedChatRequest, LLMProvider
from ..utils.log import log


class TooluseTransformer(Transformer):
    """ToolUse Transformer - Adds tool mode functionality"""
    
    TransformerName = "tooluse"
    
    def __init__(self, options: Optional[TransformerOptions] = None):
        super().__init__(options)
        # The name will be set from TransformerName in the base class
    
    async def transform_request_in(
        self, 
        request: Union[UnifiedChatRequest, Dict[str, Any]], 
        provider: LLMProvider = None
    ) -> Union[Dict[str, Any], TransformRequestResult]:
        """Transform request input, adding tool mode system prompt"""
        
        # Convert request to dict if it's an object
        request_dict = request.__dict__ if hasattr(request, '__dict__') else request
        
        # Add system prompt
        system_message = {
            "role": "system",
            "content": """<system-reminder>Tool mode is active. The user expects you to proactively execute the most suitable tool to help complete the task. 
Before invoking a tool, you must carefully evaluate whether it matches the current task. If no available tool is appropriate for the task, you MUST call the `ExitTool` to exit tool mode — this is the only valid way to terminate tool mode.
Always prioritize completing the user's task effectively and efficiently by using tools whenever appropriate.</system-reminder>"""
        }
        
        if "messages" in request_dict:
            request_dict["messages"].append(system_message)
        
        # If there are tools, add ExitTool and set tool_choice to required
        if "tools" in request_dict and request_dict["tools"]:
            request_dict["tool_choice"] = "required"
            
            # Add ExitTool to the beginning of the tools list
            exit_tool = {
                "type": "function",
                "function": {
                    "name": "ExitTool",
                    "description": """Use this tool when you are in tool mode and have completed the task. This is the only valid way to exit tool mode.
IMPORTANT: Before using this tool, ensure that none of the available tools are applicable to the current task. You must evaluate all available options — only if no suitable tool can help you complete the task should you use ExitTool to terminate tool mode.
Examples:
1. Task: "Use a tool to summarize this document" — Do not use ExitTool if a summarization tool is available.
2. Task: "What's the weather today?" — If no tool is available to answer, use ExitTool after reasoning that none can fulfill the task.""",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "response": {
                                "type": "string",
                                "description": "Your response will be forwarded to the user exactly as returned — the tool will not modify or post-process it in any way."
                            }
                        },
                        "required": ["response"]
                    }
                }
            }
            
            request_dict["tools"].insert(0, exit_tool)
        
        return request_dict
    
    async def transform_response_out(self, response: httpx.Response) -> httpx.Response:
        """Transform response output, handling ExitTool calls"""
        content_type = response.headers.get("Content-Type", "")
        
        if "application/json" in content_type:
            # Handle non-streaming response
            try:
                json_response = await response.json()
                
                # Check for ExitTool call
                if (json_response.get("choices") and 
                    len(json_response["choices"]) > 0 and
                    json_response["choices"][0].get("message", {}).get("tool_calls") and
                    len(json_response["choices"][0]["message"]["tool_calls"]) > 0 and
                    json_response["choices"][0]["message"]["tool_calls"][0].get("function", {}).get("name") == "ExitTool"):
                    
                    tool_call = json_response["choices"][0]["message"]["tool_calls"][0]
                    try:
                        tool_arguments = json.loads(tool_call["function"].get("arguments", "{}"))
                        json_response["choices"][0]["message"]["content"] = tool_arguments.get("response", "")
                        del json_response["choices"][0]["message"]["tool_calls"]
                    except json.JSONDecodeError:
                        log.error("Failed to parse ExitTool arguments")
                
                return httpx.Response(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    content=json.dumps(json_response).encode('utf-8')
                )
            except Exception as e:
                log.error(f"Error processing JSON response: {str(e)}")
                return response
            
        elif "stream" in content_type:
            # Handle streaming response
            if not hasattr(response, 'aiter_bytes'):
                return response
            
            # Create a streaming response that processes the stream on-the-fly
            async def process_stream():
                exit_tool_index = -1
                exit_tool_response = ""
                
                async for chunk in response.aiter_bytes():
                    chunk_str = chunk.decode('utf-8')
                    lines = chunk_str.split('\n')
                    
                    for line in lines:
                        if not line.strip():
                            continue
                            
                        if line.startswith("data: ") and line.strip() != "data: [DONE]":
                            try:
                                data = json.loads(line[6:])
                                
                                # Check for tool calls
                                if (data.get("choices") and 
                                    len(data["choices"]) > 0 and
                                    data["choices"][0].get("delta", {}).get("tool_calls")):
                                    
                                    tool_call = data["choices"][0]["delta"]["tool_calls"][0]
                                    
                                    # Check if it's ExitTool
                                    if tool_call.get("function", {}).get("name") == "ExitTool":
                                        exit_tool_index = tool_call.get("index", 0)
                                        continue
                                    elif (exit_tool_index > -1 and 
                                          tool_call.get("index") == exit_tool_index and 
                                          tool_call.get("function", {}).get("arguments")):
                                        
                                        exit_tool_response += tool_call["function"]["arguments"]
                                        try:
                                            # Try to parse the response if we have enough data
                                            response_obj = json.loads(exit_tool_response)
                                            data["choices"] = [{
                                                "delta": {
                                                    "role": "assistant",
                                                    "content": response_obj.get("response", "")
                                                }
                                            }]
                                            modified_line = f"data: {json.dumps(data)}\n\n"
                                            yield modified_line.encode('utf-8')
                                        except json.JSONDecodeError:
                                            # If we can't parse yet, continue collecting
                                            pass
                                        continue
                                
                                # Send valid deltas
                                if (data.get("choices") and 
                                    len(data["choices"]) > 0 and
                                    data["choices"][0].get("delta") and 
                                    len(data["choices"][0]["delta"]) > 0):
                                    modified_line = f"data: {json.dumps(data)}\n\n"
                                    yield modified_line.encode('utf-8')
                                    
                            except json.JSONDecodeError:
                                # JSON parsing failed, pass through the original line
                                yield (line + "\n").encode('utf-8')
                        elif line.strip() == "data: [DONE]":
                            # Pass through the DONE marker
                            yield (line + "\n\n").encode('utf-8')
                        else:
                            # Pass through non-data lines
                            yield (line + "\n").encode('utf-8')
            
            # Return a streaming response
            return StreamingResponse(
                content=process_stream(),
                status_code=response.status_code,
                media_type="text/event-stream",
                headers={
                    "Content-Type": "text/event-stream",
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive"
                }
            )
        
        return response