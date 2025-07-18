from typing import Dict, Any, Optional, Protocol
from abc import ABC, abstractmethod
import httpx

from .llm import LLMProvider, UnifiedChatRequest


class TransformerOptions(Dict[str, Any]):
    pass


class Transformer(ABC):
    """转换器基类"""
    
    def __init__(self, options: Optional[TransformerOptions] = None):
        self.options = options or {}
        self.name: Optional[str] = None
        self.end_point: Optional[str] = None
    
    async def transform_request_in(
        self, 
        request: UnifiedChatRequest, 
        provider: LLMProvider
    ) -> Dict[str, Any]:
        """将统一请求格式转换为提供者特定格式"""
        return request.__dict__
    
    async def transform_response_in(self, response: httpx.Response) -> httpx.Response:
        """转换响应输入"""
        return response
    
    async def transform_request_out(self, request: Any) -> UnifiedChatRequest:
        """将提供者特定格式转换为统一请求格式"""
        if isinstance(request, dict):
            return UnifiedChatRequest(**request)
        return request
    
    async def transform_response_out(self, response: httpx.Response) -> httpx.Response:
        """转换响应输出"""
        return response


class TransformerConstructor(Protocol):
    """转换器构造器协议"""
    
    def __call__(self, options: Optional[TransformerOptions] = None) -> Transformer:
        ...
    
    @property
    def TransformerName(self) -> Optional[str]:
        ...


class TransformerWithStaticName(Transformer):
    """带有静态名称的转换器"""
    TransformerName: Optional[str] = None