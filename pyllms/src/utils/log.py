import os
import json
from datetime import datetime

def log(*args):
    """
    记录日志信息
    
    参数:
        *args: 要记录的消息
    """
    # 打印到控制台
    print(*args)
    
    # 检查是否启用日志记录
    is_log_enabled = os.environ.get("LOG") == "true"
    
    if not is_log_enabled:
        return
    
    # 格式化日志消息
    timestamp = datetime.now().isoformat()
    log_message = f"[{timestamp}] "
    
    if args:
        formatted_args = []
        for arg in args:
            if isinstance(arg, (dict, list)):
                formatted_args.append(json.dumps(arg))
            else:
                formatted_args.append(str(arg))
        log_message += " ".join(formatted_args)
    
    log_message += "\n"
    
    # 追加到日志文件
    log_file = os.environ.get("LOG_FILE", "app.log")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(log_message)