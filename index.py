import asyncio
import json
import os
import signal
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from constants import CONFIG_FILE
from utils import init_config, init_dir
from server import create_server
from utils.router import router
from middleware.auth import api_key_auth
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from utils.process_check import (
    cleanup_pid_file,
    is_service_running,
    save_pid,
)

async def initialize_claude_config():
    """Initialize Claude configuration file"""
    home_dir = Path.home()
    config_path = home_dir / ".claude.json"
    
    if not config_path.exists():
        user_id = ''.join([hex(int(15 * __import__('random').random()))[2:] for _ in range(64)])
        config_content = {
            "numStartups": 184,
            "autoUpdaterStatus": "enabled",
            "userID": user_id,
            "hasCompletedOnboarding": True,
            "lastOnboardingVersion": "1.0.17",
            "projects": {},
        }
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_content, f, indent=2)

async def run(options: Optional[Dict[str, Any]] = None):
    """Run the service"""
    if options is None:
        options = {}
    
    # Check if service is already running
    if is_service_running():
        print("✅ Service is already running in the background.")
        return
    
    await initialize_claude_config()
    await init_dir()
    config = await init_config()
    
    host = config.get("HOST", "127.0.0.1")
    
    if config.get("HOST") and not config.get("APIKEY"):
        host = "127.0.0.1"
        print("⚠️ API key is not set. HOST is forced to 127.0.0.1.")
    
    port = options.get("port", 3456)
    
    # Save the PID of the background process
    save_pid(os.getpid())
    
    # Handle SIGINT (Ctrl+C) to clean up PID file
    def signal_handler(signum, frame):
        print("Received signal, cleaning up...")
        cleanup_pid_file()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print(host)
    
    # Use port from environment variable if set (for background process)
    service_port = int(os.environ.get("SERVICE_PORT", port))
    
    # 创建原始服务器
    server = create_server({
        "json_path": str(CONFIG_FILE),
        "initial_config": {
            "providers": config.get("Providers") or config.get("providers"),
            "HOST": host,
            "PORT": service_port,
            "LOG_FILE": str(Path.home() / ".claude-code-router" / "claude-code-router.log"),
        },
    })
    
    # 创建一个适配器函数，使其与我们的中间件系统兼容
    async def router_adapter(req, reply):
        await router(req, reply, config)
    
    # 创建一个适配器函数，用于处理认证
    async def auth_adapter(req, reply):
        # 创建一个简单的响应对象
        class SimpleResponse:
            def __init__(self):
                self.status_code = 200
                self.body = None
                self.headers = {}
        
        # 如果 reply 为 None，创建一个简单的响应对象
        if reply is None:
            reply = SimpleResponse()
        
        # 调用认证中间件
        auth_middleware = api_key_auth(config)
        await auth_middleware(req, reply)
    
    # 创建一个新的日志记录中间件，用于验证回调是否被调用
    async def log_callback_adapter(req, reply):
        print("=" * 50)
        print("LOG: 新的 pre_handler 回调被调用!")
        print(f"LOG: [{ __import__('datetime').datetime.now().isoformat() }] 请求路径: {req.url.path}")
        print(f"LOG: 请求方法: {req.method}")
        
        # 提取请求头中的授权信息
        auth_header = req.headers.get("authorization", "")
        if auth_header and auth_header.startswith("Bearer "):
            api_key = auth_header.split("Bearer ")[1].strip()
            # 打印可直接复制到终端的环境变量设置命令
            print("\n# 复制以下命令到终端设置环境变量:")
            print(f"export OPENAI_API_KEY='{api_key}'")
            print(f"export ANTHROPIC_API_KEY='{api_key}'")
            print(f"export CLAUDE_API_KEY='{api_key}'")
            print("# 或者在 Windows PowerShell 中使用:")
            print(f"$env:OPENAI_API_KEY='{api_key}'")
            print(f"$env:ANTHROPIC_API_KEY='{api_key}'")
            print(f"$env:CLAUDE_API_KEY='{api_key}'")
            print("# 或者在 Windows CMD 中使用:")
            print(f"set OPENAI_API_KEY={api_key}")
            print(f"set ANTHROPIC_API_KEY={api_key}")
            print(f"set CLAUDE_API_KEY={api_key}")
        
        # 打印所有请求头，可能包含其他有用信息
        print("\n# 所有请求头:")
        for key, value in req.headers.items():
            print(f"# {key}: {value}")
        
        print("=" * 50)
        
        # 如果需要，可以修改请求或响应
        # 例如，添加一个自定义头部
        if reply and hasattr(reply, "headers"):
            reply.headers["X-Custom-Header"] = "pre_handler_called"
    
    # 添加中间件，注意顺序很重要：先日志记录，再认证，最后路由
    # server.add_hook("pre_handler", log_callback_adapter)
    # server.add_hook("pre_handler", auth_adapter)
    # server.add_hook("pre_handler", router_adapter)
    
    try:
        # Start the server (now runs in a separate thread)
        await server.start()
        
        # Keep the main thread alive to handle signals
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        cleanup_pid_file()

if __name__ == "__main__":
    asyncio.run(run())