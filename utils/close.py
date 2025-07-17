import os
import signal
from pathlib import Path

from .process_check import is_service_running, cleanup_pid_file, get_reference_count
from ..constants import HOME_DIR

async def close_service():
    """Close the service if no references remain"""
    pid_file = HOME_DIR / ".claude-code-router.pid"
    
    if not is_service_running():
        print("No service is currently running.")
        return
    
    if get_reference_count() > 0:
        return
    
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        cleanup_pid_file()
        print("claude code router service has been successfully stopped.")
    except (OSError, ValueError, FileNotFoundError):
        print("Failed to stop the service. It may have already been stopped.")
        cleanup_pid_file()