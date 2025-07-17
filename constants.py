import os
from pathlib import Path

HOME_DIR = Path.home() / ".claude-code-router"
CONFIG_FILE = HOME_DIR / "config.json"
PLUGINS_DIR = HOME_DIR / "plugins"
PID_FILE = HOME_DIR / ".claude-code-router.pid"
REFERENCE_COUNT_FILE = Path("/tmp") / "claude-code-reference-count.txt"

DEFAULT_CONFIG = {
    "LOG": False,
    "OPENAI_API_KEY": "",
    "OPENAI_BASE_URL": "",
    "OPENAI_MODEL": "",
}