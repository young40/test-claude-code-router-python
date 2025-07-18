from typing import Dict, List, Optional, Any

from .provider import ProviderService
from ..types.llm import LLMProvider, RegisterProviderRequest, RequestRouteInfo


class LLMService:
    """LLM服务类，负责管理LLM提供者"""
    
    def __init__(self, provider_service: ProviderService):
        self.provider_service = provider_service
    
    def register_provider(self, request: RegisterProviderRequest) -> LLMProvider:
        """注册LLM提供者"""
        return self.provider_service.register_provider(request)
    
    def get_providers(self) -> List[LLMProvider]:
        """获取所有LLM提供者"""
        return self.provider_service.get_providers()
    
    def get_provider(self, id: str) -> Optional[LLMProvider]:
        """获取指定ID的LLM提供者"""
        return self.provider_service.get_provider(id)
    
    def update_provider(self, id: str, updates: Dict[str, Any]) -> Optional[LLMProvider]:
        """更新LLM提供者"""
        result = self.provider_service.update_provider(id, updates)
        return result
    
    def delete_provider(self, id: str) -> bool:
        """删除LLM提供者"""
        result = self.provider_service.delete_provider(id)
        return result
    
    def toggle_provider(self, id: str, enabled: bool) -> bool:
        """切换LLM提供者状态"""
        return self.provider_service.toggle_provider(id, enabled)
    
    def _resolve_route(self, model_name: str) -> RequestRouteInfo:
        """解析模型路由"""
        route = self.provider_service.resolve_model_route(model_name)
        if not route:
            raise ValueError(
                f"Model {model_name} not found. Available models: {', '.join(self.get_available_model_names())}"
            )
        return route
    
    async def get_available_models(self) -> Dict[str, Any]:
        """获取可用模型列表"""
        providers = self.provider_service.get_available_models()
        
        return {
            "object": "list",
            "data": [
                {
                    "id": model,
                    "object": "model",
                    "provider": provider["provider"],
                    "created": int(datetime.now().timestamp()),
                    "owned_by": provider["provider"],
                }
                for provider in providers
                for model in provider["models"]
            ]
        }
    
    def get_available_model_names(self) -> List[str]:
        """获取可用模型名称列表"""
        return [route.full_model for route in self.provider_service.get_model_routes()]
    
    def get_model_routes(self):
        """获取模型路由"""
        return self.provider_service.get_model_routes()