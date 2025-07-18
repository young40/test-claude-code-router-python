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
    # Use silent mode if running in background
    silent_mode = options.get("silent", False)
    config = await init_config(silent=silent_mode)
    
    host = config.get("HOST", "127.0.0.1")
    
    if config.get("HOST") and not config.get("APIKEY"):
        host = "127.0.0.1"
        if not silent_mode:
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
    
    if not silent_mode:
        print(host)
    
    # Use port from environment variable if set (for background process)
    service_port = int(os.environ.get("SERVICE_PORT", port))
    
    server = create_server({
        "json_path": str(CONFIG_FILE),
        "initial_config": {
            "providers": config.get("Providers") or config.get("providers"),
            "HOST": host,
            "PORT": service_port,
            "LOG_FILE": str(Path.home() / ".claude-code-router" / "claude-code-router.log"),
        },
    })
    
    server.add_hook("pre_handler", api_key_auth(config))
    server.add_hook("pre_handler", lambda req, reply: asyncio.create_task(router(req, reply, config)))
    
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