#!/usr/bin/env python3
import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import List

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from index import run
from utils.status import show_status
from utils.code_command import execute_code_command
from utils.process_check import cleanup_pid_file, is_service_running
from constants import PID_FILE, REFERENCE_COUNT_FILE

VERSION = "1.0.0"

HELP_TEXT = f"""
Usage: python3 cli.py [command]

Commands:
  start         Start service 
  stop          Stop service
  status        Show service status
  code          Execute code command
  -v, version   Show version information
  -h, help      Show help information

Example:
  python3 cli.py start
  python3 cli.py code "Write a Hello World"
"""

async def wait_for_service(timeout: int = 10000, initial_delay: int = 1000) -> bool:
    """Wait for service to start"""
    # Wait for an initial period to let the service initialize
    await asyncio.sleep(initial_delay / 1000)
    
    start_time = time.time() * 1000
    while (time.time() * 1000) - start_time < timeout:
        if is_service_running():
            # Wait for an additional short period to ensure service is fully ready
            await asyncio.sleep(0.5)
            return True
        await asyncio.sleep(0.1)
    return False

async def main():
    """Main CLI function"""
    command = sys.argv[1] if len(sys.argv) > 1 else None
    
    if command == "start":
        # Check if --silent flag is provided
        silent_mode = "--silent" in sys.argv
        await run({"silent": silent_mode})
    
    elif command == "stop":
        try:
            if PID_FILE.exists():
                pid = int(PID_FILE.read_text().strip())
                os.kill(pid, signal.SIGTERM)
                cleanup_pid_file()
                if REFERENCE_COUNT_FILE.exists():
                    try:
                        REFERENCE_COUNT_FILE.unlink()
                    except OSError:
                        # Ignore cleanup errors
                        pass
                print("claude code router service has been successfully stopped.")
            else:
                print("No PID file found. Service may not be running.")
        except (OSError, ValueError, FileNotFoundError):
            print("Failed to stop the service. It may have already been stopped.")
            cleanup_pid_file()
    
    elif command == "status":
        show_status()
    
    elif command == "code":
        if not is_service_running():
            print("Service not running, starting service...")
            cli_path = Path(__file__).resolve()
            
            try:
                # Start service in background with silent mode
                process = subprocess.Popen(
                    [sys.executable, str(cli_path), "start", "--silent"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                
                if await wait_for_service():
                    await execute_code_command(sys.argv[2:])
                else:
                    print("Service startup timeout, please manually run `python3 cli.py start` to start the service")
                    sys.exit(1)
            except Exception as error:
                print(f"Failed to start service: {error}")
                sys.exit(1)
        else:
            await execute_code_command(sys.argv[2:])
    
    elif command in ["-v", "version"]:
        print(f"claude-code-router version: {VERSION}")
    
    elif command in ["-h", "help"]:
        print(HELP_TEXT)
    
    else:
        print(HELP_TEXT)
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)