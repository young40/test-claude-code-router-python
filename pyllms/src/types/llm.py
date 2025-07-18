from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass
from enum import Enum


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


@dataclass
class TextContent:
    type: str = "text"
    text: str = ""
    cache_control: Optional[Dict[str, Any]] = None


@dataclass
class ImageContent:
    type: str = "image"
    image_url: Dict[str, str] = None
    
    def __post_init__(self):
        if self.image_url is None:
            self.image_url = {"url": "", "detail": "auto"}


MessageContent = Union[TextContent, ImageContent]


@dataclass
class ToolCall:
    id: str
    type: str = "function"
    function: Dict[str, str] = None
    
    def __post_init__(self):
        if self.function is None:
            self.function = {"name": "", "arguments": ""}


@dataclass
class ThinkingContent:
    content: str
    signature: Optional[str] = None


@dataclass
class UnifiedMessage:
    role: MessageRole
    content: Optional[Union[str, List[MessageContent]]] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    cache_control: Optional[Dict[str, Any]] = None
    thinking: Optional[ThinkingContent] = None


@dataclass
class UnifiedTool:
    type: str = "function"
    function: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.function is None:
            self.function = {
                "name": "",
                "description": "",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }


@dataclass
class UnifiedChatRequest:
    messages: List[UnifiedMessage]
    model: str
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    stream: Optional[bool] = False
    tools: Optional[List[UnifiedTool]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class UnifiedChatResponse:
    id: str
    model: str
    content: Optional[str] = None
    usage: Optional[Usage] = None
    tool_calls: Optional[List[ToolCall]] = None


@dataclass
class StreamChunk:
    id: str
    object: str
    created: int
    model: str
    choices: Optional[List[Dict[str, Any]]] = None


@dataclass
class LLMProvider:
    name: str
    base_url: str
    api_key: str
    models: List[str]
    transformer: Optional[Dict[str, Any]] = None


RegisterProviderRequest = LLMProvider


@dataclass
class ModelRoute:
    provider: str
    model: str
    full_model: str


@dataclass
class RequestRouteInfo:
    provider: LLMProvider
    original_model: str
    target_model: str


@dataclass
class ConfigProvider:
    name: str
    api_base_url: str
    api_key: str
    models: List[str]
    transformer: Optional[Dict[str, Any]] = None