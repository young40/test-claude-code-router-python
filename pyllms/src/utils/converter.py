import json
from typing import Dict, List, Any, Optional, Union, Tuple

from ..types.llm import (
    UnifiedMessage, UnifiedChatRequest, UnifiedTool, ToolCall,
    MessageRole, TextContent, ImageContent
)
from .log import log


def convert_tools_to_openai(tools: List[UnifiedTool]) -> List[Dict[str, Any]]:
    """将统一工具格式转换为OpenAI格式"""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.function["name"],
                "description": tool.function["description"],
                "parameters": tool.function["parameters"]
            }
        }
        for tool in tools
    ]


def convert_tools_to_anthropic(tools: List[UnifiedTool]) -> List[Dict[str, Any]]:
    """将统一工具格式转换为Anthropic格式"""
    return [
        {
            "name": tool.function["name"],
            "description": tool.function["description"],
            "input_schema": tool.function["parameters"]
        }
        for tool in tools
    ]


def convert_tools_from_openai(tools: List[Dict[str, Any]]) -> List[UnifiedTool]:
    """将OpenAI工具格式转换为统一格式"""
    return [
        UnifiedTool(
            type="function",
            function={
                "name": tool["function"]["name"],
                "description": tool["function"].get("description", ""),
                "parameters": tool["function"]["parameters"]
            }
        )
        for tool in tools
    ]


def convert_tools_from_anthropic(tools: List[Dict[str, Any]]) -> List[UnifiedTool]:
    """将Anthropic工具格式转换为统一格式"""
    return [
        UnifiedTool(
            type="function",
            function={
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool["input_schema"]
            }
        )
        for tool in tools
    ]


def is_tool_call_content(content: str) -> bool:
    """检查内容是否为工具调用格式"""
    try:
        parsed = json.loads(content)
        return (
            isinstance(parsed, list) and
            any(
                isinstance(item, dict) and 
                item.get("type") == "tool_use" and 
                item.get("id") and 
                item.get("name")
                for item in parsed
            )
        )
    except (json.JSONDecodeError, TypeError):
        return False


def convert_to_openai(request: UnifiedChatRequest) -> Dict[str, Any]:
    """将统一请求格式转换为OpenAI格式"""
    messages = []
    tool_responses_queue = {}  # 用于存储工具响应
    
    # 收集工具响应
    for msg in request.messages:
        if msg.role == MessageRole.TOOL and msg.tool_call_id:
            if msg.tool_call_id not in tool_responses_queue:
                tool_responses_queue[msg.tool_call_id] = []
            tool_responses_queue[msg.tool_call_id].append({
                "role": "tool",
                "content": msg.content,
                "tool_call_id": msg.tool_call_id
            })
    
    # 处理消息
    for msg in request.messages:
        if msg.role == MessageRole.TOOL:
            continue
        
        message = {
            "role": msg.role.value,
            "content": msg.content
        }
        
        if msg.tool_calls:
            message["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": tool_call.type,
                    "function": {
                        "name": tool_call.function["name"],
                        "arguments": tool_call.function["arguments"]
                    }
                }
                for tool_call in msg.tool_calls
            ]
            if message["content"] is None:
                message["content"] = None
        
        messages.append(message)
        
        # 处理工具调用后的响应
        if (msg.role == MessageRole.ASSISTANT and 
            msg.tool_calls):
            for tool_call in msg.tool_calls:
                if tool_call.id in tool_responses_queue:
                    responses = tool_responses_queue[tool_call.id]
                    messages.extend(responses)
                    del tool_responses_queue[tool_call.id]
                else:
                    # 添加默认响应
                    messages.append({
                        "role": "tool",
                        "content": json.dumps({
                            "success": True,
                            "message": "Tool call executed successfully",
                            "tool_call_id": tool_call.id
                        }),
                        "tool_call_id": tool_call.id
                    })
    
    # 添加剩余的工具响应
    for responses in tool_responses_queue.values():
        messages.extend(responses)
    
    # 构建结果
    result = {
        "messages": messages,
        "model": request.model,
        "max_tokens": request.max_tokens,
        "temperature": request.temperature,
        "stream": request.stream
    }
    
    # 添加工具
    if request.tools:
        result["tools"] = convert_tools_to_openai(request.tools)
        if request.tool_choice:
            if request.tool_choice in ["auto", "none"]:
                result["tool_choice"] = request.tool_choice
            else:
                result["tool_choice"] = {
                    "type": "function",
                    "function": {"name": request.tool_choice}
                }
    
    return result


def convert_from_openai(request: Dict[str, Any]) -> UnifiedChatRequest:
    """将OpenAI请求格式转换为统一格式"""
    messages = []
    
    for msg in request["messages"]:
        role = MessageRole(msg["role"])
        
        # 处理助手消息中的工具调用内容
        if (role == MessageRole.ASSISTANT and 
            isinstance(msg.get("content"), str) and 
            is_tool_call_content(msg["content"])):
            try:
                tool_calls_data = json.loads(msg["content"])
                converted_tool_calls = [
                    ToolCall(
                        id=call["id"],
                        type="function",
                        function={
                            "name": call["name"],
                            "arguments": json.dumps(call.get("input", {}))
                        }
                    )
                    for call in tool_calls_data
                ]
                
                messages.append(UnifiedMessage(
                    role=role,
                    content=None,
                    tool_calls=converted_tool_calls
                ))
                continue
            except (json.JSONDecodeError, KeyError):
                pass
        
        # 处理工具消息
        if role == MessageRole.TOOL:
            content = msg["content"]
            if not isinstance(content, str):
                content = json.dumps(content)
            
            messages.append(UnifiedMessage(
                role=role,
                content=content,
                tool_call_id=msg.get("tool_call_id")
            ))
            continue
        
        # 处理普通消息
        content = msg["content"]
        if not isinstance(content, str):
            content = json.dumps(content)
        
        tool_calls = None
        if msg.get("tool_calls"):
            tool_calls = [
                ToolCall(
                    id=tc["id"],
                    type=tc["type"],
                    function=tc["function"]
                )
                for tc in msg["tool_calls"]
            ]
        
        messages.append(UnifiedMessage(
            role=role,
            content=content,
            tool_calls=tool_calls
        ))
    
    # 构建结果
    result = UnifiedChatRequest(
        messages=messages,
        model=request["model"],
        max_tokens=request.get("max_tokens"),
        temperature=request.get("temperature"),
        stream=request.get("stream")
    )
    
    # 处理工具
    if request.get("tools"):
        result.tools = convert_tools_from_openai(request["tools"])
        
        if request.get("tool_choice"):
            tool_choice = request["tool_choice"]
            if isinstance(tool_choice, str):
                result.tool_choice = tool_choice
            elif isinstance(tool_choice, dict) and tool_choice.get("type") == "function":
                result.tool_choice = tool_choice["function"]["name"]
    
    return result


def convert_from_anthropic(request: Dict[str, Any]) -> UnifiedChatRequest:
    """将Anthropic请求格式转换为统一格式"""
    messages = []
    
    # 处理系统消息
    if request.get("system"):
        messages.append(UnifiedMessage(
            role=MessageRole.SYSTEM,
            content=request["system"]
        ))
    
    pending_tool_calls = []
    pending_text_content = []
    last_role = None
    
    # 处理消息
    for msg in request["messages"]:
        role = MessageRole(msg["role"])
        content = msg["content"]
        
        if isinstance(content, str):
            # 处理待处理的助手工具调用
            if (last_role == "assistant" and 
                pending_tool_calls and 
                role != MessageRole.ASSISTANT):
                assistant_message = UnifiedMessage(
                    role=MessageRole.ASSISTANT,
                    content="".join(pending_text_content) or None,
                    tool_calls=pending_tool_calls if pending_tool_calls else None
                )
                if assistant_message.tool_calls and not pending_text_content:
                    assistant_message.content = None
                messages.append(assistant_message)
                pending_tool_calls.clear()
                pending_text_content.clear()
            
            messages.append(UnifiedMessage(
                role=role,
                content=content
            ))
            
        elif isinstance(content, list):
            text_blocks = []
            tool_calls = []
            tool_results = []
            
            # 分类内容块
            for block in content:
                if block.get("type") == "text":
                    text_blocks.append(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    tool_calls.append(ToolCall(
                        id=block["id"],
                        type="function",
                        function={
                            "name": block["name"],
                            "arguments": json.dumps(block.get("input", {}))
                        }
                    ))
                elif block.get("type") == "tool_result":
                    tool_results.append(block)
            
            # 处理工具结果
            if tool_results:
                if last_role == "assistant" and pending_tool_calls:
                    assistant_message = UnifiedMessage(
                        role=MessageRole.ASSISTANT,
                        content="".join(pending_text_content) or None,
                        tool_calls=pending_tool_calls
                    )
                    if not pending_text_content:
                        assistant_message.content = None
                    messages.append(assistant_message)
                    pending_tool_calls.clear()
                    pending_text_content.clear()
                
                for tool_result in tool_results:
                    content_str = tool_result["content"]
                    if not isinstance(content_str, str):
                        content_str = json.dumps(content_str)
                    
                    messages.append(UnifiedMessage(
                        role=MessageRole.TOOL,
                        content=content_str,
                        tool_call_id=tool_result["tool_use_id"]
                    ))
            
            # 处理助手消息
            elif role == MessageRole.ASSISTANT:
                if last_role == "assistant":
                    pending_tool_calls.extend(tool_calls)
                    pending_text_content.extend(text_blocks)
                else:
                    if pending_tool_calls:
                        prev_assistant_message = UnifiedMessage(
                            role=MessageRole.ASSISTANT,
                            content="".join(pending_text_content) or None,
                            tool_calls=pending_tool_calls
                        )
                        if not pending_text_content:
                            prev_assistant_message.content = None
                        messages.append(prev_assistant_message)
                    
                    pending_tool_calls.clear()
                    pending_text_content.clear()
                    pending_tool_calls.extend(tool_calls)
                    pending_text_content.extend(text_blocks)
            
            # 处理其他消息
            else:
                if last_role == "assistant" and pending_tool_calls:
                    assistant_message = UnifiedMessage(
                        role=MessageRole.ASSISTANT,
                        content="".join(pending_text_content) or None,
                        tool_calls=pending_tool_calls
                    )
                    if not pending_text_content:
                        assistant_message.content = None
                    messages.append(assistant_message)
                    pending_tool_calls.clear()
                    pending_text_content.clear()
                
                message = UnifiedMessage(
                    role=role,
                    content="".join(text_blocks) or None
                )
                
                if tool_calls:
                    message.tool_calls = tool_calls
                    if not text_blocks:
                        message.content = None
                
                messages.append(message)
        
        else:
            # 处理其他类型的内容
            if last_role == "assistant" and pending_tool_calls:
                assistant_message = UnifiedMessage(
                    role=MessageRole.ASSISTANT,
                    content="".join(pending_text_content) or None,
                    tool_calls=pending_tool_calls
                )
                if not pending_text_content:
                    assistant_message.content = None
                messages.append(assistant_message)
                pending_tool_calls.clear()
                pending_text_content.clear()
            
            messages.append(UnifiedMessage(
                role=role,
                content=json.dumps(content)
            ))
        
        last_role = role.value
    
    # 处理最后的待处理助手消息
    if last_role == "assistant" and pending_tool_calls:
        assistant_message = UnifiedMessage(
            role=MessageRole.ASSISTANT,
            content="".join(pending_text_content) or None,
            tool_calls=pending_tool_calls
        )
        if not pending_text_content:
            assistant_message.content = None
        messages.append(assistant_message)
    
    # 构建结果
    result = UnifiedChatRequest(
        messages=messages,
        model=request["model"],
        max_tokens=request.get("max_tokens"),
        temperature=request.get("temperature"),
        stream=request.get("stream")
    )
    
    # 处理工具
    if request.get("tools"):
        result.tools = convert_tools_from_anthropic(request["tools"])
        
        if request.get("tool_choice"):
            tool_choice = request["tool_choice"]
            if tool_choice.get("type") == "auto":
                result.tool_choice = "auto"
            elif tool_choice.get("type") == "tool":
                result.tool_choice = tool_choice.get("name")
    
    return result


def convert_to_anthropic(request: UnifiedChatRequest) -> Dict[str, Any]:
    """将统一请求格式转换为Anthropic格式"""
    messages = []
    system_content = None
    
    # 提取系统消息
    for msg in request.messages:
        if msg.role == MessageRole.SYSTEM:
            system_content = msg.content
            break
    
    # 处理其他消息
    for msg in request.messages:
        if msg.role == MessageRole.SYSTEM:
            continue
        
        role = "model" if msg.role == MessageRole.ASSISTANT else "user"
        content = []
        
        # 处理文本内容
        if isinstance(msg.content, str):
            content.append({"type": "text", "text": msg.content})
        elif isinstance(msg.content, list):
            for item in msg.content:
                if hasattr(item, 'type') and item.type == "text":
                    content.append({"type": "text", "text": getattr(item, 'text', '')})
        
        # 处理工具调用
        if msg.tool_calls:
            for tool_call in msg.tool_calls:
                try:
                    input_data = json.loads(tool_call.function.get("arguments", "{}"))
                except json.JSONDecodeError:
                    input_data = {}
                
                content.append({
                    "type": "tool_use",
                    "id": tool_call.id,
                    "name": tool_call.function.get("name", ""),
                    "input": input_data
                })
        
        # 处理工具结果
        if msg.role == MessageRole.TOOL and msg.tool_call_id:
            content.append({
                "type": "tool_result",
                "tool_use_id": msg.tool_call_id,
                "content": msg.content
            })
        
        if content:
            messages.append({
                "role": role,
                "content": content
            })
    
    # 构建结果
    result = {
        "messages": messages,
        "model": request.model,
        "max_tokens": request.max_tokens,
        "temperature": request.temperature,
        "stream": request.stream
    }
    
    if system_content:
        result["system"] = system_content
    
    # 处理工具
    if request.tools:
        result["tools"] = convert_tools_to_anthropic(request.tools)
        
        if request.tool_choice:
            if request.tool_choice == "auto":
                result["tool_choice"] = {"type": "auto"}
            else:
                result["tool_choice"] = {
                    "type": "tool",
                    "name": request.tool_choice
                }
    
    return result


def convert_request(
    request: Dict[str, Any],
    source_provider: str,
    target_provider: str
) -> Dict[str, Any]:
    """转换请求格式"""
    
    # 转换为统一格式
    if source_provider == "openai":
        unified_request = convert_from_openai(request)
    elif source_provider == "anthropic":
        unified_request = convert_from_anthropic(request)
    else:
        unified_request = UnifiedChatRequest(**request)
    
    # 转换为目标格式
    if target_provider == "openai":
        return convert_to_openai(unified_request)
    elif target_provider == "anthropic":
        return convert_to_anthropic(unified_request)
    else:
        return unified_request.__dict__