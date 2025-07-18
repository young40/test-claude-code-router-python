import importlib
import sys
from typing import Dict, List, Optional, Any, Union, Callable, Type

from ..utils.log import log
from .config import ConfigService
from ..types.transformer import Transformer, TransformerConstructor


class TransformerService:
    """转换器服务类，负责管理转换器"""
    
    def __init__(self, config_service: ConfigService):
        self.config_service = config_service
        self.transformers: Dict[str, Union[Transformer, TransformerConstructor]] = {}
    
    def register_transformer(self, name: str, transformer: Union[Transformer, TransformerConstructor]) -> None:
        """注册转换器"""
        self.transformers[name] = transformer
        endpoint_info = f" (endpoint: {transformer.end_point})" if hasattr(transformer, 'end_point') and transformer.end_point else " (no endpoint)"
        log(f"register transformer: {name}{endpoint_info}")
    
    def get_transformer(self, name: str) -> Optional[Union[Transformer, TransformerConstructor]]:
        """获取转换器"""
        return self.transformers.get(name)
    
    def get_all_transformers(self) -> Dict[str, Union[Transformer, TransformerConstructor]]:
        """获取所有转换器"""
        return self.transformers.copy()
    
    def get_transformers_with_endpoint(self) -> List[Dict[str, Any]]:
        """获取带有端点的转换器"""
        result = []
        
        for name, transformer in self.transformers.items():
            if hasattr(transformer, 'end_point') and transformer.end_point:
                result.append({"name": name, "transformer": transformer})
        
        return result
    
    def get_transformers_without_endpoint(self) -> List[Dict[str, Any]]:
        """获取没有端点的转换器"""
        result = []
        
        for name, transformer in self.transformers.items():
            if not hasattr(transformer, 'end_point') or not transformer.end_point:
                result.append({"name": name, "transformer": transformer})
        
        return result
    
    def remove_transformer(self, name: str) -> bool:
        """移除转换器"""
        if name in self.transformers:
            del self.transformers[name]
            return True
        return False
    
    def has_transformer(self, name: str) -> bool:
        """检查转换器是否存在"""
        return name in self.transformers
    
    async def register_transformer_from_config(self, config: Dict[str, Any]) -> bool:
        """从配置注册转换器"""
        try:
            if config.get("path"):
                # 动态导入模块
                module = importlib.import_module(config["path"])
                if module:
                    # 创建实例
                    instance = module.Transformer(config.get("options", {}))
                    if not hasattr(instance, 'name'):
                        raise ValueError(f"Transformer instance from {config['path']} does not have a name property.")
                    
                    self.register_transformer(instance.name, instance)
                    return True
            return False
        except Exception as error:
            log(f"load transformer ({config.get('path')}) error:", error)
            return False
    
    def initialize(self) -> None:
        """初始化转换器服务"""
        try:
            # 注册默认转换器
            self.register_default_transformers()
            
            # 从配置加载转换器
            self.load_from_config()
        except Exception as error:
            log("TransformerService init error:", error)
    
    def register_default_transformers(self) -> None:
        """注册默认转换器"""
        try:
            # 导入转换器模块
            from ..transformer import transformers
            
            # 注册所有转换器
            for transformer_class in transformers.values():
                if hasattr(transformer_class, 'TransformerName') and isinstance(transformer_class.TransformerName, str):
                    self.register_transformer(transformer_class.TransformerName, transformer_class)
                else:
                    transformer_instance = transformer_class()
                    if hasattr(transformer_instance, 'name'):
                        self.register_transformer(transformer_instance.name, transformer_instance)
        except Exception as error:
            log("transformer regist error:", error)
    
    def load_from_config(self) -> None:
        """从配置加载转换器"""
        transformers_config = self.config_service.get("transformers", [])
        for transformer_config in transformers_config:
            self.register_transformer_from_config(transformer_config)