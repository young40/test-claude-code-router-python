import os
from datetime import datetime
from pathlib import Path
from typing import Any

from ..constants import HOME_DIR

LOG_FILE = HOME_DIR / "claude-code-router.log"

# Ensure log directory exists
HOME_DIR.mkdir(parents=True, exist_ok=True)

def log(*args: Any):
    """Log messages to file if logging is enabled"""
    # Check if logging is enabled via environment variable
    is_log_enabled = os.environ.get("LOG") == "true"
    
    if not is_log_enabled:
        return
    
    timestamp = datetime.now().isoformat()
    log_message = f"[{timestamp}] {' '.join(str(arg) for arg in args)}\n"
    
    # Append to log file
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_message)