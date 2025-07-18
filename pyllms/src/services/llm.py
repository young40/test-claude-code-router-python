from typing import List, Optional, Dict, Any

from .provider import ProviderService
from ..types.llm import LLMProvider, RegisterProviderRequest, RequestRouteInfo


class LLMService:
    """LLM服务类"""
    
    def __init__(self, provider_service: ProviderService):
        self.provider_service = provider_service
    
    def register_provider(self, request: RegisterProviderRequest) -> LLMProvider:
        """注册提供者"""
        return self.provider_service.register_provider(request)
    
    def get_providers(self) -> List[LLMProvider]:
        """获取所有提供者"""
        return self.provider_service.get_providers()
    
    def get_provider(self, provider_id: str) -> Optional[LLMProvider]:
        """获取指定提供者"""
        return self.provider_service.get_provider(provider_id)
    
    def update_provider(
        self, 
        provider_id: str, 
        updates: Dict[str, Any]
    ) -> Optional[LLMProvider]:
        """更新提供者"""
        return self.provider_service.update_provider(provider_id, updates)
    
    def delete_provider(self, provider_id: str) -> bool:
        """删除提供者"""
        return self.provider_service.delete_provider(provider_id)
    
    def toggle_provider(self, provider_id: str, enabled: bool) -> bool:
        """切换提供者状态"""
        return self.provider_service.toggle_provider(provider_id, enabled)
    
    def _resolve_route(self, model_name: str) -> RequestRouteInfo:
        """解析模型路由"""
        route = self.provider_service.resolve_model_route(model_name)
        if not route:
            available_models = self._get_available_model_names()
            raise ValueError(
                f"Model {model_name} not found. Available models: {', '.join(available_models)}"
            )
        return route
    
    async def get_available_models(self) -> Dict[str, Any]:
        """获取可用模型列表"""
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
        """获取可用模型名称列表"""
        return [route.full_model for route in self.provider_service.get_model_routes()]
    
    def get_model_routes(self):
        """获取模型路由"""
        return self.provider_service.get_model_routes()