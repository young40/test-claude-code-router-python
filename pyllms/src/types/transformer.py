from typing import Dict, Any, Optional, Protocol, Union, TypedDict
from abc import ABC, abstractmethod
import httpx

from .llm import LLMProvider, UnifiedChatRequest


class TransformerOptions(Dict[str, Any]):
    """Options for transformer initialization"""
    pass


class TransformRequestResult(TypedDict, total=False):
    """Result of a request transformation that includes both body and config"""
    body: Dict[str, Any]
    config: Dict[str, Any]


class Transformer(ABC):
    """Transformer base class"""
    
    def __init__(self, options: Optional[TransformerOptions] = None):
        self.options = options or {}
        self.name: Optional[str] = None
        self.end_point: Optional[str] = None
    
    async def transform_request_in(
        self, 
        request: Union[UnifiedChatRequest, Dict[str, Any]], 
        provider: LLMProvider
    ) -> Union[Dict[str, Any], TransformRequestResult]:
        """
        Transform unified request format to provider-specific format
        
        This method can return either:
        - A dictionary with the transformed request
        - A TransformRequestResult with both body and config
        """
        return request.__dict__ if hasattr(request, '__dict__') else request
    
    async def transform_response_in(self, response: httpx.Response) -> httpx.Response:
        """
        Transform provider response to unified response format
        
        This is called after all transformResponseOut methods have been applied.
        This method should be used to convert provider-specific response formats
        to the unified format expected by the client.
        """
        return response
    
    async def transform_request_out(
        self, 
        request: Any
    ) -> Union[UnifiedChatRequest, Dict[str, Any], TransformRequestResult]:
        """
        Transform provider-specific format to unified request format
        
        This method can return either:
        - A UnifiedChatRequest object
        - A dictionary with the transformed request
        - A TransformRequestResult with both body and config
        """
        if isinstance(request, dict):
            return UnifiedChatRequest(**request)
        return request
    
    async def transform_response_out(self, response: httpx.Response) -> httpx.Response:
        """
        Transform provider response
        
        This is called before transformResponseIn and should be used to modify
        the provider's response before it's transformed to the unified format.
        This method is typically used by utility transformers that need to
        modify the response content but not change its format.
        """
        return response


class TransformerConstructor(Protocol):
    """Transformer constructor protocol"""
    
    def __call__(self, options: Optional[TransformerOptions] = None) -> Transformer:
        """Create a new transformer instance"""
        ...
    
    @property
    def TransformerName(self) -> Optional[str]:
        """Static transformer name"""
        ...


class TransformerWithStaticName(Transformer):
    """Transformer with static name"""
    TransformerName: Optional[str] = None