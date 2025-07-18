from typing import Dict, Any, Optional, Protocol, Union
from abc import ABC, abstractmethod
import httpx

from .llm import LLMProvider, UnifiedChatRequest


class TransformerOptions(Dict[str, Any]):
    pass


class Transformer(ABC):
    """Transformer base class"""
    
    def __init__(self, options: Optional[TransformerOptions] = None):
        self.options = options or {}
        self.name: Optional[str] = None
        self.end_point: Optional[str] = None
    
    async def transform_request_in(
        self, 
        request: UnifiedChatRequest, 
        provider: LLMProvider
    ) -> Dict[str, Any]:
        """Transform unified request format to provider-specific format"""
        return request.__dict__ if hasattr(request, '__dict__') else request
    
    async def transform_response_in(self, response: httpx.Response) -> httpx.Response:
        """Transform response input"""
        return response
    
    async def transform_request_out(self, request: Any) -> Union[UnifiedChatRequest, Dict[str, Any]]:
        """Transform provider-specific format to unified request format"""
        if isinstance(request, dict):
            return UnifiedChatRequest(**request)
        return request
    
    async def transform_response_out(self, response: httpx.Response) -> httpx.Response:
        """Transform response output"""
        return response


class TransformerConstructor(Protocol):
    """Transformer constructor protocol"""
    
    def __call__(self, options: Optional[TransformerOptions] = None) -> Transformer:
        ...
    
    @property
    def TransformerName(self) -> Optional[str]:
        ...


class TransformerWithStaticName(Transformer):
    """Transformer with static name"""
    TransformerName: Optional[str] = None