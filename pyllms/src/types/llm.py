from typing import Dict, List, Optional, Union, Any, TypedDict
from dataclasses import dataclass, field
from enum import Enum


class MessageRole(str, Enum):
    """Message roles that match TypeScript implementation"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class CacheControl(TypedDict, total=False):
    """Cache control options"""
    type: Optional[str]


@dataclass
class TextContent:
    """Text content that matches TypeScript TextContent interface"""
    type: str = "text"
    text: str = ""
    cache_control: Optional[CacheControl] = None


@dataclass
class ImageContent:
    """Image content that matches TypeScript ImageContent interface"""
    type: str = "image"
    image_url: Dict[str, str] = field(default_factory=lambda: {"url": "", "detail": "auto"})


MessageContent = Union[TextContent, ImageContent]


class FunctionCall(TypedDict):
    """Function call structure for tool calls"""
    name: str
    arguments: str


@dataclass
class ToolCall:
    """Tool call that matches TypeScript interface"""
    id: str
    type: str = "function"
    function: FunctionCall = field(default_factory=lambda: {"name": "", "arguments": ""})


class ThinkingContent(TypedDict, total=False):
    """Thinking content structure"""
    content: str
    signature: Optional[str]


@dataclass
class UnifiedMessage:
    """Unified message that matches TypeScript UnifiedMessage interface"""
    role: str  # Using str instead of MessageRole for better compatibility
    content: Optional[Union[str, List[MessageContent]]] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    cache_control: Optional[CacheControl] = None
    thinking: Optional[ThinkingContent] = None


class ToolParameters(TypedDict, total=False):
    """Tool parameters structure that matches TypeScript interface"""
    type: str
    properties: Dict[str, Any]
    required: List[str]
    additionalProperties: bool
    schema: str  # Changed from $schema to schema


class ToolFunction(TypedDict):
    """Tool function structure that matches TypeScript interface"""
    name: str
    description: str
    parameters: ToolParameters


@dataclass
class UnifiedTool:
    """Unified tool that matches TypeScript UnifiedTool interface"""
    type: str = "function"
    function: ToolFunction = field(default_factory=lambda: {
        "name": "",
        "description": "",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    })


@dataclass
class UnifiedChatRequest:
    """Unified chat request that matches TypeScript UnifiedChatRequest interface"""
    messages: List[Union[UnifiedMessage, Dict[str, Any]]]
    model: str
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    stream: Optional[bool] = False
    tools: Optional[List[Union[UnifiedTool, Dict[str, Any]]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    
    def __post_init__(self):
        # Convert dict messages to UnifiedMessage objects if needed
        if self.messages and isinstance(self.messages, list):
            for i, msg in enumerate(self.messages):
                if isinstance(msg, dict):
                    role = msg.get('role', 'user')
                    content = msg.get('content')
                    tool_calls = msg.get('tool_calls')
                    tool_call_id = msg.get('tool_call_id')
                    
                    # Convert tool_calls if present
                    if tool_calls and isinstance(tool_calls, list):
                        processed_tool_calls = []
                        for tc in tool_calls:
                            if isinstance(tc, dict):
                                processed_tool_calls.append(ToolCall(
                                    id=tc.get('id', ''),
                                    type=tc.get('type', 'function'),
                                    function=tc.get('function', {})
                                ))
                            else:
                                processed_tool_calls.append(tc)
                        tool_calls = processed_tool_calls
                    
                    # Create UnifiedMessage
                    self.messages[i] = UnifiedMessage(
                        role=role,
                        content=content,
                        tool_calls=tool_calls,
                        tool_call_id=tool_call_id,
                        cache_control=msg.get('cache_control'),
                        thinking=msg.get('thinking')
                    )
        
        # Convert dict tools to UnifiedTool objects if needed
        if self.tools and isinstance(self.tools, list):
            for i, tool in enumerate(self.tools):
                if isinstance(tool, dict):
                    self.tools[i] = UnifiedTool(
                        type=tool.get('type', 'function'),
                        function=tool.get('function', {})
                    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the UnifiedChatRequest to a dictionary for serialization"""
        result = {
            "model": self.model,
            "stream": self.stream if self.stream is not None else False,
        }
        
        # Add optional fields if they exist
        if self.max_tokens is not None:
            result["max_tokens"] = self.max_tokens
        
        if self.temperature is not None:
            result["temperature"] = self.temperature
        
        if self.tool_choice is not None:
            result["tool_choice"] = self.tool_choice
        
        # Process messages
        messages = []
        for msg in self.messages:
            if isinstance(msg, UnifiedMessage):
                message_dict = {"role": msg.role}
                
                # Handle content
                if msg.content is not None:
                    message_dict["content"] = msg.content
                
                # Handle tool calls
                if msg.tool_calls:
                    tool_calls_list = []
                    for tc in msg.tool_calls:
                        if isinstance(tc, ToolCall):
                            tool_calls_list.append({
                                "id": tc.id,
                                "type": tc.type,
                                "function": tc.function
                            })
                        else:
                            tool_calls_list.append(tc)
                    message_dict["tool_calls"] = tool_calls_list
                
                # Handle tool call id
                if msg.tool_call_id:
                    message_dict["tool_call_id"] = msg.tool_call_id
                
                # Handle cache control
                if msg.cache_control:
                    message_dict["cache_control"] = msg.cache_control
                
                # Handle thinking
                if msg.thinking:
                    message_dict["thinking"] = {
                        "content": msg.thinking.content
                    }
                    if msg.thinking.signature:
                        message_dict["thinking"]["signature"] = msg.thinking.signature
                
                messages.append(message_dict)
            else:
                # If it's already a dict, use it as is
                messages.append(msg)
        
        result["messages"] = messages
        
        # Process tools
        if self.tools:
            tools_list = []
            for tool in self.tools:
                if isinstance(tool, UnifiedTool):
                    tools_list.append({
                        "type": tool.type,
                        "function": tool.function
                    })
                else:
                    # If it's already a dict, use it as is
                    tools_list.append(tool)
            
            result["tools"] = tools_list
        
        return result
    
    def __str__(self) -> str:
        """String representation of the request"""
        import json
        return json.dumps(self.to_dict())


@dataclass
class Usage:
    """Usage information that matches TypeScript interface"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class UnifiedChatResponse:
    """Unified chat response that matches TypeScript UnifiedChatResponse interface"""
    id: str
    model: str
    content: Optional[str] = None
    usage: Optional[Usage] = None
    tool_calls: Optional[List[ToolCall]] = None


class StreamDelta(TypedDict, total=False):
    """Stream delta structure that matches TypeScript interface"""
    role: Optional[str]
    content: Optional[str]
    tool_calls: Optional[List[Dict[str, Any]]]


class StreamChoice(TypedDict, total=False):
    """Stream choice structure that matches TypeScript interface"""
    index: int
    delta: StreamDelta
    finish_reason: Optional[str]


@dataclass
class StreamChunk:
    """Stream chunk that matches TypeScript StreamChunk interface"""
    id: str
    object: str
    created: int
    model: str
    choices: Optional[List[StreamChoice]] = None


@dataclass
class LLMProvider:
    """LLM provider that matches TypeScript LLMProvider interface"""
    name: str
    base_url: str  # Using snake_case as per Python conventions (baseUrl in TypeScript)
    api_key: str
    models: List[str]
    transformer: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        # Ensure transformer structure is initialized properly
        if self.transformer is None:
            self.transformer = {}
        
        # Ensure the 'use' field exists at the top level
        if 'use' not in self.transformer:
            self.transformer['use'] = []


# Define RegisterProviderRequest as the same type as LLMProvider
RegisterProviderRequest = LLMProvider


@dataclass
class ModelRoute:
    """Model route that matches TypeScript ModelRoute interface"""
    provider: str
    model: str
    full_model: str  # Renamed from fullModel to follow Python naming conventions


@dataclass
class RequestRouteInfo:
    """Request route info that matches TypeScript RequestRouteInfo interface"""
    provider: LLMProvider
    original_model: str  # Renamed from originalModel to follow Python naming conventions
    target_model: str    # Renamed from targetModel to follow Python naming conventions


@dataclass
class ConfigProvider:
    """Config provider that matches TypeScript ConfigProvider interface"""
    name: str
    api_base_url: str  # Using snake_case as per Python conventions
    api_key: str
    models: List[str]
    transformer: Optional[Dict[str, Any]] = None