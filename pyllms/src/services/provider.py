from typing import Dict, List, Optional, Any, Union, Type
from datetime import datetime

from ..types.llm import LLMProvider, RegisterProviderRequest, ModelRoute, RequestRouteInfo, ConfigProvider
from ..utils.log import log
from .config import ConfigService
from .transformer import TransformerService


class ProviderService:
    """提供者服务类，负责管理LLM提供者和模型路由"""
    
    def __init__(self, config_service: ConfigService, transformer_service: TransformerService):
        self.config_service = config_service
        self.transformer_service = transformer_service
        self.providers: Dict[str, LLMProvider] = {}
        self.model_routes: Dict[str, ModelRoute] = {}
        
        self.initialize_custom_providers()
    
    def initialize_custom_providers(self):
        """初始化自定义提供者"""
        providers_config = self.config_service.get("providers")
        if providers_config and isinstance(providers_config, list):
            self.initialize_from_providers_array(providers_config)
    
    def initialize_from_providers_array(self, providers_config: List[ConfigProvider]):
        """从提供者配置数组初始化"""
        for provider_config in providers_config:
            try:
                if not (provider_config.get("name") and 
                        provider_config.get("api_base_url") and 
                        provider_config.get("api_key")):
                    continue
                
                transformer = {}
                
                if provider_config.get("transformer"):
                    for key, value in provider_config["transformer"].items():
                        if key == "use":
                            if isinstance(value, list):
                                transformer["use"] = []
                                for t in value:
                                    if isinstance(t, list) and isinstance(t[0], str):
                                        constructor = self.transformer_service.get_transformer(t[0])
                                        if constructor:
                                            transformer["use"].append(constructor(t[1]))
                                    elif isinstance(t, str):
                                        t_instance = self.transformer_service.get_transformer(t)
                                        if t_instance:
                                            transformer["use"].append(t_instance)
                        else:
                            if isinstance(provider_config["transformer"].get(key, {}).get("use"), list):
                                transformer[key] = {
                                    "use": []
                                }
                                for t in provider_config["transformer"][key]["use"]:
                                    if isinstance(t, list) and isinstance(t[0], str):
                                        constructor = self.transformer_service.get_transformer(t[0])
                                        if constructor:
                                            transformer[key]["use"].append(constructor(t[1]))
                                    elif isinstance(t, str):
                                        t_instance = self.transformer_service.get_transformer(t)
                                        if t_instance:
                                            transformer[key]["use"].append(t_instance)
                
                self.register_provider({
                    "name": provider_config["name"],
                    "base_url": provider_config["api_base_url"],
                    "api_key": provider_config["api_key"],
                    "models": provider_config.get("models", []),
                    "transformer": transformer if provider_config.get("transformer") else None
                })
                
                log(f"{provider_config['name']} provider registered")
            except Exception as error:
                log(f"{provider_config['name']} provider registered error: {error}")
    
    def register_provider(self, request: RegisterProviderRequest) -> LLMProvider:
        """注册提供者"""
        provider = {**request}
        
        self.providers[provider["name"]] = provider
        
        for model in request["models"]:
            full_model = f"{provider['name']},{model}"
            route = {
                "provider": provider["name"],
                "model": model,
                "full_model": full_model
            }
            self.model_routes[full_model] = route
            if model not in self.model_routes:
                self.model_routes[model] = route
        
        return provider
    
    def get_providers(self) -> List[LLMProvider]:
        """获取所有提供者"""
        return list(self.providers.values())
    
    def get_provider(self, name: str) -> Optional[LLMProvider]:
        """获取指定名称的提供者"""
        return self.providers.get(name)
    
    def update_provider(self, id: str, updates: Dict[str, Any]) -> Optional[LLMProvider]:
        """更新提供者"""
        provider = self.providers.get(id)
        if not provider:
            return None
        
        updated_provider = {
            **provider,
            **updates,
            "updated_at": datetime.now()
        }
        
        self.providers[id] = updated_provider
        
        if "models" in updates:
            # 删除旧模型路由
            for model in provider["models"]:
                full_model = f"{provider['name']},{model}"
                if full_model in self.model_routes:
                    del self.model_routes[full_model]
                if model in self.model_routes and self.model_routes[model]["provider"] == provider["name"]:
                    del self.model_routes[model]
            
            # 添加新模型路由
            for model in updates["models"]:
                full_model = f"{provider['name']},{model}"
                route = {
                    "provider": provider["name"],
                    "model": model,
                    "full_model": full_model
                }
                self.model_routes[full_model] = route
                if model not in self.model_routes:
                    self.model_routes[model] = route
        
        return updated_provider
    
    def delete_provider(self, id: str) -> bool:
        """删除提供者"""
        provider = self.providers.get(id)
        if not provider:
            return False
        
        # 删除相关模型路由
        for model in provider["models"]:
            full_model = f"{provider['name']},{model}"
            if full_model in self.model_routes:
                del self.model_routes[full_model]
            if model in self.model_routes and self.model_routes[model]["provider"] == provider["name"]:
                del self.model_routes[model]
        
        # 删除提供者
        del self.providers[id]
        return True
    
    def toggle_provider(self, name: str, enabled: bool) -> bool:
        """切换提供者状态"""
        provider = self.providers.get(name)
        if not provider:
            return False
        return True
    
    def resolve_model_route(self, model_name: str) -> Optional[RequestRouteInfo]:
        """解析模型路由"""
        route = self.model_routes.get(model_name)
        if not route:
            return None
        
        provider = self.providers.get(route["provider"])
        if not provider:
            return None
        
        return {
            "provider": provider,
            "original_model": model_name,
            "target_model": route["model"]
        }
    
    def get_available_model_names(self) -> List[str]:
        """获取可用模型名称列表"""
        model_names = []
        for provider in self.providers.values():
            for model in provider["models"]:
                model_names.append(model)
                model_names.append(f"{provider['name']},{model}")
        return model_names
    
    def get_model_routes(self) -> List[ModelRoute]:
        """获取模型路由列表"""
        return list(self.model_routes.values())
    
    def parse_transformer_config(self, transformer_config: Any) -> Dict[str, Any]:
        """解析转换器配置"""
        if not transformer_config:
            return {}
        
        if isinstance(transformer_config, list):
            result = {}
            for item in transformer_config:
                if isinstance(item, list):
                    name, config = item[0], item[1] if len(item) > 1 else {}
                    result[name] = config
                else:
                    result[item] = {}
            return result
        
        return transformer_config
    
    async def get_available_models(self) -> Dict[str, Any]:
        """获取可用模型"""
        models = []
        
        for provider in self.providers.values():
            for model in provider["models"]:
                models.append({
                    "id": model,
                    "object": "model",
                    "owned_by": provider["name"],
                    "provider": provider["name"]
                })
                
                models.append({
                    "id": f"{provider['name']},{model}",
                    "object": "model",
                    "owned_by": provider["name"],
                    "provider": provider["name"]
                })
        
        return {
            "object": "list",
            "data": models
        }