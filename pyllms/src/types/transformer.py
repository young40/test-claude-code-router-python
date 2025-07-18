from typing import Dict, Any, Optional, Protocol, Union, TypedDict, Type
from abc import ABC
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
    """Transformer base class that matches the TypeScript implementation"""
    
    def __init__(self, options: Optional[TransformerOptions] = None):
        self.options = options or {}
        self.name: Optional[str] = None
        self._end_point: Optional[str] = None
    
    @property
    def end_point(self) -> Optional[str]:
        """Get the endpoint (Python naming convention)"""
        return self._end_point
    
    @end_point.setter
    def end_point(self, value: Optional[str]):
        """Set the endpoint (Python naming convention)"""
        self._end_point = value
    
    @property
    def endPoint(self) -> Optional[str]:
        """Get the endpoint (TypeScript naming convention)"""
        return self._end_point
    
    @endPoint.setter
    def endPoint(self, value: Optional[str]):
        """Set the endpoint (TypeScript naming convention)"""
        self._end_point = value
    
    async def transform_request_in(
        self, 
        request: UnifiedChatRequest, 
        provider: LLMProvider
    ) -> Dict[str, Any]:
        """
        Transform unified request format to provider-specific format
        
        This method corresponds to transformRequestIn in TypeScript
        """
        return request.to_dict() if hasattr(request, 'to_dict') else request
    
    async def transform_response_in(self, response: httpx.Response) -> httpx.Response:
        """
        Transform provider response to unified response format
        
        This corresponds to transformResponseIn in TypeScript
        """
        return response
    
    async def transform_request_out(
        self, 
        request: Any
    ) -> UnifiedChatRequest:
        """
        Transform provider-specific format to unified request format
        
        This corresponds to transformRequestOut in TypeScript
        """
        if isinstance(request, dict):
            return UnifiedChatRequest(**request)
        return request
    
    async def transform_response_out(self, response: httpx.Response) -> httpx.Response:
        """
        Transform provider response
        
        This corresponds to transformResponseOut in TypeScript
        """
        return response


class TransformerConstructor(Protocol):
    """
    Transformer constructor protocol that matches the TypeScript TransformerConstructor
    """
    
    def __call__(self, options: Optional[TransformerOptions] = None) -> Transformer:
        """Create a new transformer instance"""
        ...
    
    TransformerName: Optional[str] = None


class TransformerWithStaticName(Transformer):
    """
    Transformer with static name that matches the TypeScript TransformerWithStaticName
    """
    TransformerName: Optional[str] = None