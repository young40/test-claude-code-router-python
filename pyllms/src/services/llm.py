from typing import List, Optional, Dict, Any

from .provider import ProviderService
from ..types.llm import LLMProvider, RegisterProviderRequest, RequestRouteInfo


class LLMService:
    """LLM Service class"""
    
    def __init__(self, provider_service: ProviderService):
        self.provider_service = provider_service
    
    def register_provider(self, request: RegisterProviderRequest) -> LLMProvider:
        """Register a provider"""
        return self.provider_service.register_provider(request)
    
    def get_providers(self) -> List[LLMProvider]:
        """Get all providers"""
        return self.provider_service.get_providers()
    
    def get_provider(self, provider_id: str) -> Optional[LLMProvider]:
        """Get a specific provider by ID"""
        return self.provider_service.get_provider(provider_id)
    
    def update_provider(
        self, 
        provider_id: str, 
        updates: Dict[str, Any]
    ) -> Optional[LLMProvider]:
        """Update a provider"""
        return self.provider_service.update_provider(provider_id, updates)
    
    def delete_provider(self, provider_id: str) -> bool:
        """Delete a provider"""
        return self.provider_service.delete_provider(provider_id)
    
    def toggle_provider(self, provider_id: str, enabled: bool) -> bool:
        """Toggle provider enabled status"""
        return self.provider_service.toggle_provider(provider_id, enabled)
    
    def _resolve_route(self, model_name: str) -> RequestRouteInfo:
        """Resolve model route"""
        route = self.provider_service.resolve_model_route(model_name)
        if not route:
            available_models = self._get_available_model_names()
            from ..api.middleware import create_api_error
            raise create_api_error(
                f"Model '{model_name}' not found. Available models: {', '.join(available_models)}",
                404,
                "model_not_found"
            )
        return route
    
    async def get_available_models(self) -> Dict[str, Any]:
        """Get available models"""
        providers = await self.provider_service.get_available_models()
        
        return {
            "object": "list",
            "data": [
                model for provider in providers["data"]
                for model in [{
                    "id": model_name,
                    "object": "model",
                    "provider": provider["provider"],
                    "created": int(__import__('time').time()),
                    "owned_by": provider["provider"]
                } for model_name in provider.get("models", [])]
            ]
        }
    
    def _get_available_model_names(self) -> List[str]:
        """Get available model names"""
        return [route.full_model for route in self.provider_service.get_model_routes()]
    
    def get_model_routes(self):
        """Get model routes"""
        return self.provider_service.get_model_routes()