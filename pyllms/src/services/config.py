import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, field


@dataclass
class ConfigOptions:
    env_path: Optional[str] = ".env"
    json_path: Optional[str] = "./config.json"
    use_env_file: bool = False
    use_json_file: bool = True
    use_environment_variables: bool = True
    initial_config: Optional[Dict[str, Any]] = None


class ConfigService:
    """配置服务类"""
    
    def __init__(self, options: Optional[ConfigOptions] = None):
        if options is None:
            options = ConfigOptions()
        
        self.options = options
        self.config: Dict[str, Any] = {}
        
        self.load_config()
    
    def load_config(self) -> None:
        """加载配置"""
        if self.options.use_json_file and self.options.json_path:
            self._load_json_config()
        
        if self.options.initial_config:
            self.config.update(self.options.initial_config)
        
        if self.options.use_env_file:
            self._load_env_config()
        
        # 设置日志环境变量
        if self.config.get("LOG_FILE"):
            os.environ["LOG_FILE"] = str(self.config["LOG_FILE"])
        if self.config.get("LOG"):
            os.environ["LOG"] = str(self.config["LOG"])
    
    def _load_json_config(self) -> None:
        """加载JSON配置文件"""
        if not self.options.json_path:
            return
        
        json_path = Path(self.options.json_path)
        if not json_path.is_absolute():
            json_path = Path.cwd() / json_path
        
        if json_path.exists():
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    json_config = json.load(f)
                self.config.update(json_config)
                print(f"Loaded JSON config from: {json_path}")
            except Exception as error:
                print(f"Failed to load JSON config from {json_path}: {error}")
        else:
            print(f"JSON config file not found: {json_path}")
    
    def _load_env_config(self) -> None:
        """加载环境变量配置文件"""
        if not self.options.env_path:
            return
        
        env_path = Path(self.options.env_path)
        if not env_path.is_absolute():
            env_path = Path.cwd() / env_path
        
        if env_path.exists():
            try:
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            self.config[key.strip()] = value.strip()
            except Exception as error:
                print(f"Failed to load .env config from {env_path}: {error}")
    
    def get(self, key: str, default_value: Any = None) -> Any:
        """获取配置值"""
        return self.config.get(key, default_value)
    
    def get_all(self) -> Dict[str, Any]:
        """获取所有配置"""
        return self.config.copy()
    
    def get_https_proxy(self) -> Optional[str]:
        """获取HTTPS代理配置"""
        return (
            self.get("HTTPS_PROXY") or
            self.get("https_proxy") or
            self.get("httpsProxy") or
            self.get("PROXY_URL")
        )
    
    def has(self, key: str) -> bool:
        """检查是否存在配置项"""
        return key in self.config
    
    def set(self, key: str, value: Any) -> None:
        """设置配置值"""
        self.config[key] = value
    
    def reload(self) -> None:
        """重新加载配置"""
        self.config.clear()
        self.load_config()
    
    def get_config_summary(self) -> str:
        """获取配置摘要"""
        summary = []
        
        if self.options.initial_config:
            summary.append("Initial Config")
        
        if self.options.use_json_file and self.options.json_path:
            summary.append(f"JSON: {self.options.json_path}")
        
        if self.options.use_env_file:
            summary.append(f"ENV: {self.options.env_path}")
        
        if self.options.use_environment_variables:
            summary.append("Environment Variables")
        
        return f"Config sources: {', '.join(summary)}"