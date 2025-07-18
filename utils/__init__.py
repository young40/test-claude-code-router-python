import json
import os
import sys
from pathlib import Path
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from constants import CONFIG_FILE, DEFAULT_CONFIG, HOME_DIR, PLUGINS_DIR

def ensure_dir(dir_path: Path):
    """Ensure directory exists"""
    dir_path.mkdir(parents=True, exist_ok=True)

async def init_dir():
    """Initialize required directories"""
    ensure_dir(HOME_DIR)
    ensure_dir(PLUGINS_DIR)

def question(query: str) -> str:
    """Ask user for input"""
    return input(query)

async def confirm(query: str) -> bool:
    """Ask user for confirmation"""
    answer = question(query)
    return answer.lower() != "n"

async def read_config_file(silent: bool = False) -> Dict[str, Any]:
    """Read configuration file or create one if it doesn't exist"""
    if not silent:
        print(f"📁 Config file path: {CONFIG_FILE}")
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            if not silent:
                print(f"✅ Config file found and loaded")
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠️ Config file not found, creating new one...")
        name = question("Enter Provider Name: ")
        api_key = question("Enter Provider API KEY: ")
        base_url = question("Enter Provider URL: ")
        model = question("Enter MODEL Name: ")
        
        config = {
            **DEFAULT_CONFIG,
            "Providers": [
                {
                    "name": name,
                    "api_base_url": base_url,
                    "api_key": api_key,
                    "models": [model],
                }
            ],
            "Router": {
                "default": f"{name},{model}",
            },
        }
        await write_config_file(config)
        return config

async def write_config_file(config: Dict[str, Any]):
    """Write configuration to file"""
    ensure_dir(HOME_DIR)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)

async def init_config(silent: bool = False) -> Dict[str, Any]:
    """Initialize configuration and set environment variables"""
    config = await read_config_file(silent=silent)
    for key, value in config.items():
        if isinstance(value, str):
            os.environ[key] = value
    return config