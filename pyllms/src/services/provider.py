import time
from typing import Dict, List, Optional, Any
from datetime import datetime

from ..types.llm import (
    LLMProvider, RegisterProviderRequest, ModelRoute, 
    RequestRouteInfo, ConfigProvider
)
from ..utils.log import log
from .config import ConfigService
from .transformer import TransformerService


class ProviderService:
    """提供者服务类"""
    
    def __init__(self, config_service: ConfigService, transformer_service: TransformerService):
        self.config_service = config_service
        self.transformer_service = transformer_service
        self.providers: Dict[str, LLMProvider] = {}
        self.model_routes: Dict[str, ModelRoute] = {}
        
        self._initialize_custom_providers()
    
    def _initialize_custom_providers(self) -> None:
        """初始化自定义提供者"""
        # 尝试使用 "providers" 或 "Providers" 键
        providers_config = self.config_service.get("providers") or self.config_service.get("Providers")
        if providers_config and isinstance(providers_config, list):
            self._initialize_from_providers_array(providers_config)
    
    def _initialize_from_providers_array(self, providers_config: List[Dict[str, Any]]) -> None:
        """从提供者配置数组初始化"""
        for provider_config in providers_config:
            try:
                if not all([
                    provider_config.get("name"),
                    provider_config.get("api_base_url"),
                    provider_config.get("api_key")
                ]):
                    continue
                
                transformer = {}
                
                if provider_config.get("transformer"):
                    transformer_config = provider_config["transformer"]
                    
                    for key, value in transformer_config.items():
                        if key == "use":
                            if isinstance(value, list):
                                transformer["use"] = []
                                for transformer_item in value:
                                    if isinstance(transformer_item, list) and len(transformer_item) >= 1:
                                        transformer_class = self.transformer_service.get_transformer(transformer_item[0])
                                        if transformer_class:
                                            options = transformer_item[1] if len(transformer_item) > 1 else None
                                            transformer["use"].append(transformer_class(options))
                                    elif isinstance(transformer_item, str):
                                        transformer_class = self.transformer_service.get_transformer(transformer_item)
                                        if transformer_class:
                                            transformer["use"].append(transformer_class())
                        else:
                            if isinstance(value, dict) and isinstance(value.get("use"), list):
                                transformer[key] = {"use": []}
                                for transformer_item in value["use"]:
                                    if isinstance(transformer_item, list) and len(transformer_item) >= 1:
                                        transformer_class = self.transformer_service.get_transformer(transformer_item[0])
                                        if transformer_class:
                                            options = transformer_item[1] if len(transformer_item) > 1 else None
                                            transformer[key]["use"].append(transformer_class(options))
                                    elif isinstance(transformer_item, str):
                                        transformer_class = self.transformer_service.get_transformer(transformer_item)
                                        if transformer_class:
                                            transformer[key]["use"].append(transformer_class())
                
                self.register_provider(RegisterProviderRequest(
                    name=provider_config["name"],
                    base_url=provider_config["api_base_url"],
                    api_key=provider_config["api_key"],
                    models=provider_config.get("models", []),
                    transformer=transformer if transformer else None
                ))
                
                log(f"{provider_config['name']} provider registered")
                
            except Exception as error:
                log(f"{provider_config.get('name', 'Unknown')} provider registered error: {error}")
                # Continue with other providers even if one fails
    
    def register_provider(self, request: RegisterProviderRequest) -> LLMProvider:
        """注册提供者"""
        provider = LLMProvider(
            name=request.name,
            base_url=request.base_url,
            api_key=request.api_key,
            models=request.models,
            transformer=request.transformer
        )
        
        self.providers[provider.name] = provider
        
        # 注册模型路由
        for model in request.models:
            full_model = f"{provider.name},{model}"
            route = ModelRoute(
                provider=provider.name,
                model=model,
                full_model=full_model
            )
            self.model_routes[full_model] = route
            if model not in self.model_routes:
                self.model_routes[model] = route
        
        return provider
    
    def get_providers(self) -> List[LLMProvider]:
        """获取所有提供者"""
        return list(self.providers.values())
    
    def get_provider(self, name: str) -> Optional[LLMProvider]:
        """获取指定提供者"""
        return self.providers.get(name)
    
    def update_provider(
        self, 
        provider_id: str, 
        updates: Dict[str, Any]
    ) -> Optional[LLMProvider]:
        """更新提供者"""
        provider = self.providers.get(provider_id)
        if not provider:
            return None
        
        # 更新提供者信息
        for key, value in updates.items():
            if hasattr(provider, key):
                setattr(provider, key, value)
        
        self.providers[provider_id] = provider
        
        # 如果更新了模型列表，需要重新注册路由
        if "models" in updates:
            # 删除旧路由
            old_models = getattr(provider, 'models', [])
            for model in old_models:
                full_model = f"{provider.name},{model}"
                self.model_routes.pop(full_model, None)
                if self.model_routes.get(model) and self.model_routes[model].provider == provider.name:
                    self.model_routes.pop(model, None)
            
            # 添加新路由
            for model in updates["models"]:
                full_model = f"{provider.name},{model}"
                route = ModelRoute(
                    provider=provider.name,
                    model=model,
                    full_model=full_model
                )
                self.model_routes[full_model] = route
                if model not in self.model_routes:
                    self.model_routes[model] = route
        
        return provider
    
    def delete_provider(self, provider_id: str) -> bool:
        """删除提供者"""
        provider = self.providers.get(provider_id)
        if not provider:
            return False
        
        # 删除相关路由
        for model in provider.models:
            full_model = f"{provider.name},{model}"
            self.model_routes.pop(full_model, None)
            if self.model_routes.get(model) and self.model_routes[model].provider == provider.name:
                self.model_routes.pop(model, None)
        
        del self.providers[provider_id]
        return True
    
    def toggle_provider(self, name: str, enabled: bool) -> bool:
        """切换提供者状态"""
        provider = self.providers.get(name)
        if not provider:
            return False
        # 这里可以添加启用/禁用逻辑
        return True
    
    def resolve_model_route(self, model_name: str) -> Optional[RequestRouteInfo]:
        """解析模型路由"""
        route = self.model_routes.get(model_name)
        if not route:
            return None
        
        provider = self.providers.get(route.provider)
        if not provider:
            return None
        
        return RequestRouteInfo(
            provider=provider,
            original_model=model_name,
            target_model=route.model
        )
    
    def get_available_model_names(self) -> List[str]:
        """获取可用模型名称"""
        model_names = []
        for provider in self.providers.values():
            for model in provider.models:
                model_names.append(model)
                model_names.append(f"{provider.name},{model}")
        return model_names
    
    def get_model_routes(self) -> List[ModelRoute]:
        """获取模型路由"""
        return list(self.model_routes.values())
    
    async def get_available_models(self) -> Dict[str, Any]:
        """获取可用模型"""
        models = []
        
        for provider in self.providers.values():
            for model in provider.models:
                models.append({
                    "id": model,
                    "object": "model",
                    "owned_by": provider.name,
                    "provider": provider.name
                })
                
                models.append({
                    "id": f"{provider.name},{model}",
                    "object": "model", 
                    "owned_by": provider.name,
                    "provider": provider.name
                })
        
        return {
            "object": "list",
            "data": models
        }