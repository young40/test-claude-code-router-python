import os
import subprocess
import sys
from typing import List

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.process_check import increment_reference_count, decrement_reference_count
from utils.close import close_service
from utils import read_config_file

async def execute_code_command(args: List[str] = None):
    """Execute claude code command"""
    if args is None:
        args = ["--debug"]
    
    # Set environment variables
    config = await read_config_file()
    env = os.environ.copy()
    env.update({
        "ANTHROPIC_AUTH_TOKEN": "test",
        "ANTHROPIC_BASE_URL": "http://127.0.0.1:3456",
        "API_TIMEOUT_MS": "600000",
    })
    
    if config.get("APIKEY"):
        env["ANTHROPIC_API_KEY"] = config["APIKEY"]
        if "ANTHROPIC_AUTH_TOKEN" in env:
            del env["ANTHROPIC_AUTH_TOKEN"]
    
    # Increment reference count when command starts
    increment_reference_count()
    
    try:
        # Execute claude command
        claude_path = os.environ.get("CLAUDE_PATH", "claude")
        process = subprocess.Popen(
            [claude_path] + args,
            env=env,
            shell=True
        )
        
        # Wait for process to complete
        return_code = process.wait()
        
    except FileNotFoundError:
        print("Failed to start claude command: command not found")
        print("Make sure Claude Code is installed: npm install -g @anthropic-ai/claude-code")
        decrement_reference_count()
        sys.exit(1)
    except Exception as e:
        print(f"Failed to start claude command: {e}")
        decrement_reference_count()
        sys.exit(1)
    finally:
        decrement_reference_count()
        await close_service()
        sys.exit(return_code)