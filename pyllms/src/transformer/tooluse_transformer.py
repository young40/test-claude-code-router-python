import json
from typing import Dict, Any, Optional
import httpx

from ..types.transformer import Transformer, TransformerOptions
from ..types.llm import UnifiedChatRequest
from ..utils.log import log


class TooluseTransformer(Transformer):
    """工具使用转换器"""
    
    def __init__(self, options: Optional[TransformerOptions] = None):
        super().__init__(options)
        self.name = "tooluse"
    
    async def transform_request_in(
        self, 
        request: UnifiedChatRequest, 
        provider=None
    ) -> UnifiedChatRequest:
        """转换请求输入，添加工具模式系统提示"""
        
        # 添加系统提示
        system_message = {
            "role": "system",
            "content": """<system-reminder>Tool mode is active. The user expects you to proactively execute the most suitable tool to help complete the task. 
Before invoking a tool, you must carefully evaluate whether it matches the current task. If no available tool is appropriate for the task, you MUST call the `ExitTool` to exit tool mode — this is the only valid way to terminate tool mode.
Always prioritize completing the user's task effectively and efficiently by using tools whenever appropriate.</system-reminder>"""
        }
        
        request.messages.append(system_message)
        
        # 如果有工具，添加ExitTool并设置tool_choice为required
        if hasattr(request, 'tools') and request.tools:
            request.tool_choice = "required"
            
            # 添加ExitTool到工具列表开头
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
            
            request.tools.insert(0, exit_tool)
        
        return request
    
    async def transform_response_out(self, response: httpx.Response) -> httpx.Response:
        """转换响应输出，处理ExitTool调用"""
        content_type = response.headers.get("Content-Type", "")
        
        if "application/json" in content_type:
            # 处理非流式响应
            json_response = await response.json()
            
            # 检查是否有ExitTool调用
            if (json_response.get("choices", [{}])[0].get("message", {}).get("tool_calls") and
                json_response["choices"][0]["message"]["tool_calls"][0].get("function", {}).get("name") == "ExitTool"):
                
                tool_call = json_response["choices"][0]["message"]["tool_calls"][0]
                try:
                    tool_arguments = json.loads(tool_call.get("function", {}).get("arguments", "{}"))
                    json_response["choices"][0]["message"]["content"] = tool_arguments.get("response", "")
                    del json_response["choices"][0]["message"]["tool_calls"]
                except json.JSONDecodeError:
                    pass
            
            return httpx.Response(
                status_code=response.status_code,
                headers=response.headers,
                json=json_response
            )
            
        elif "stream" in content_type:
            # 处理流式响应
            if not hasattr(response, 'aiter_bytes'):
                return response
            
            exit_tool_index = -1
            exit_tool_response = ""
            
            async def stream_generator():
                nonlocal exit_tool_index, exit_tool_response
                
                async for chunk in response.aiter_bytes():
                    chunk_str = chunk.decode('utf-8')
                    lines = chunk_str.split('\n')
                    
                    for line in lines:
                        if line.startswith("data: ") and line.strip() != "data: [DONE]":
                            try:
                                data = json.loads(line[6:])
                                
                                # 检查工具调用
                                if data.get("choices", [{}])[0].get("delta", {}).get("tool_calls"):
                                    tool_call = data["choices"][0]["delta"]["tool_calls"][0]
                                    
                                    # 检查是否是ExitTool
                                    if tool_call.get("function", {}).get("name") == "ExitTool":
                                        exit_tool_index = tool_call.get("index", 0)
                                        continue
                                    elif (exit_tool_index > -1 and 
                                          tool_call.get("index") == exit_tool_index and 
                                          tool_call.get("function", {}).get("arguments")):
                                        
                                        exit_tool_response += tool_call["function"]["arguments"]
                                        try:
                                            response_data = json.loads(exit_tool_response)
                                            data["choices"] = [{
                                                "delta": {
                                                    "role": "assistant",
                                                    "content": response_data.get("response", "")
                                                }
                                            }]
                                            modified_line = f"data: {json.dumps(data)}\n\n"
                                            yield modified_line.encode('utf-8')
                                        except json.JSONDecodeError:
                                            pass
                                        continue
                                
                                # 发送有效的delta
                                if (data.get("choices", [{}])[0].get("delta") and 
                                    len(data["choices"][0]["delta"]) > 0):
                                    modified_line = f"data: {json.dumps(data)}\n\n"
                                    yield modified_line.encode('utf-8')
                                    
                            except json.JSONDecodeError:
                                # JSON解析失败，传递原始行
                                yield (line + "\n").encode('utf-8')
                        else:
                            # 传递非数据行
                            yield (line + "\n").encode('utf-8')
            
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