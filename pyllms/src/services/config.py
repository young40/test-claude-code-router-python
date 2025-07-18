import os
import json
from pathlib import Path
from typing import Any, Dict, Optional, TypeVar, Union
import dotenv

T = TypeVar('T')

class AppConfig(Dict[str, Any]):
    pass


class ConfigService:
    """配置服务类，负责加载和管理应用配置"""
    
    def __init__(self, options=None):
        if options is None:
            options = {"json_path": "./config.json"}
            
        self.options = {
            "env_path": options.get("env_path", ".env"),
            "json_path": options.get("json_path"),
            "use_env_file": options.get("use_env_file", False),
            "use_json_file": options.get("use_json_file", True),
            "use_environment_variables": options.get("use_environment_variables", True),
            "initial_config": options.get("initial_config", {})
        }
        
        self.config = {}
        self.load_config()
    
    def load_config(self) -> None:
        """加载配置"""
        if self.options["use_json_file"] and self.options["json_path"]:
            self.load_json_config()
        
        if self.options.get("initial_config"):
            self.config.update(self.options["initial_config"])
        
        if self.options["use_env_file"]:
            self.load_env_config()
        
        if self.options["use_environment_variables"]:
            self.load_environment_variables()
        
        # 设置日志相关环境变量
        if self.config.get("LOG_FILE"):
            os.environ["LOG_FILE"] = self.config["LOG_FILE"]
        if self.config.get("LOG"):
            os.environ["LOG"] = self.config["LOG"]
    
    def load_json_config(self) -> None:
        """从JSON文件加载配置"""
        if not self.options["json_path"]:
            return
        
        json_path = self.options["json_path"]
        if not self._is_absolute_path(json_path):
            json_path = os.path.join(os.getcwd(), json_path)
        
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    json_config = json.load(f)
                self.config.update(json_config)
                print(f"Loaded JSON config from: {json_path}")
            except Exception as error:
                print(f"Failed to load JSON config from {json_path}: {error}")
        else:
            print(f"JSON config file not found: {json_path}")
    
    def load_env_config(self) -> None:
        """从.env文件加载配置"""
        env_path = self.options["env_path"]
        if not self._is_absolute_path(env_path):
            env_path = os.path.join(os.getcwd(), env_path)
        
        if os.path.exists(env_path):
            try:
                env_vars = dotenv.dotenv_values(env_path)
                self.config.update(self._parse_env_config(env_vars))
            except Exception as error:
                print(f"Failed to load .env config from {env_path}: {error}")
    
    def load_environment_variables(self) -> None:
        """从环境变量加载配置"""
        env_config = self._parse_env_config(os.environ)
        self.config.update(env_config)
    
    def _parse_env_config(self, env: Dict[str, str]) -> Dict[str, Any]:
        """解析环境变量配置"""
        parsed = {}
        parsed.update(env)
        return parsed
    
    def _is_absolute_path(self, path: str) -> bool:
        """检查路径是否为绝对路径"""
        return path.startswith('/') or ':' in path
    
    def get(self, key: str, default_value: Optional[T] = None) -> Union[Any, T]:
        """获取配置值"""
        value = self.config.get(key)
        return value if value is not None else default_value
    
    def get_all(self) -> Dict[str, Any]:
        """获取所有配置"""
        return self.config.copy()
    
    def get_https_proxy(self) -> Optional[str]:
        """获取HTTPS代理配置"""
        return (self.get("HTTPS_PROXY") or 
                self.get("https_proxy") or 
                self.get("httpsProxy") or 
                self.get("PROXY_URL"))
    
    def has(self, key: str) -> bool:
        """检查配置是否存在"""
        return key in self.config
    
    def set(self, key: str, value: Any) -> None:
        """设置配置值"""
        self.config[key] = value
    
    def reload(self) -> None:
        """重新加载配置"""
        self.config = {}
        self.load_config()
    
    def get_config_summary(self) -> str:
        """获取配置来源摘要"""
        summary = []
        
        if self.options.get("initial_config"):
            summary.append("Initial Config")
        
        if self.options["use_json_file"] and self.options["json_path"]:
            summary.append(f"JSON: {self.options['json_path']}")
        
        if self.options["use_env_file"]:
            summary.append(f"ENV: {self.options['env_path']}")
        
        if self.options["use_environment_variables"]:
            summary.append("Environment Variables")
        
        return f"Config sources: {', '.join(summary)}"