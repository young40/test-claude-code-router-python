import os
from datetime import datetime
from pathlib import Path
from typing import Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from constants import HOME_DIR

LOG_FILE = HOME_DIR / "claude-code-router.log"

# Ensure log directory exists
HOME_DIR.mkdir(parents=True, exist_ok=True)

def log(*args: Any):
    """Log messages to console and file"""
    timestamp = datetime.now().isoformat()
    log_message = f"[{timestamp}] {' '.join(str(arg) for arg in args)}"
    
    # 总是打印到控制台
    print(f"LOG: {log_message}")
    
    # 检查是否启用了文件日志
    is_log_enabled = os.environ.get("LOG") == "true"
    
    if is_log_enabled:
        # 追加到日志文件
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_message + "\n")