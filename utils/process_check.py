import os
import signal
from pathlib import Path
from typing import Optional, Dict, Any

from ..constants import PID_FILE, REFERENCE_COUNT_FILE

def increment_reference_count():
    """Increment reference count"""
    count = 0
    if REFERENCE_COUNT_FILE.exists():
        try:
            count = int(REFERENCE_COUNT_FILE.read_text().strip()) or 0
        except (ValueError, FileNotFoundError):
            count = 0
    count += 1
    REFERENCE_COUNT_FILE.write_text(str(count))

def decrement_reference_count():
    """Decrement reference count"""
    count = 0
    if REFERENCE_COUNT_FILE.exists():
        try:
            count = int(REFERENCE_COUNT_FILE.read_text().strip()) or 0
        except (ValueError, FileNotFoundError):
            count = 0
    count = max(0, count - 1)
    REFERENCE_COUNT_FILE.write_text(str(count))

def get_reference_count() -> int:
    """Get current reference count"""
    if not REFERENCE_COUNT_FILE.exists():
        return 0
    try:
        return int(REFERENCE_COUNT_FILE.read_text().strip()) or 0
    except (ValueError, FileNotFoundError):
        return 0

def is_service_running() -> bool:
    """Check if service is running"""
    if not PID_FILE.exists():
        return False
    
    try:
        pid = int(PID_FILE.read_text().strip())
        # Check if process exists
        os.kill(pid, 0)
        return True
    except (OSError, ValueError, ProcessLookupError):
        # Process not running, clean up pid file
        cleanup_pid_file()
        return False

def save_pid(pid: int):
    """Save process ID to file"""
    PID_FILE.write_text(str(pid))

def cleanup_pid_file():
    """Clean up PID file"""
    if PID_FILE.exists():
        try:
            PID_FILE.unlink()
        except OSError:
            # Ignore cleanup errors
            pass

def get_service_pid() -> Optional[int]:
    """Get service PID"""
    if not PID_FILE.exists():
        return None
    
    try:
        pid = int(PID_FILE.read_text().strip())
        return pid if not isinstance(pid, type(None)) else None
    except (ValueError, FileNotFoundError):
        return None

def get_service_info() -> Dict[str, Any]:
    """Get service information"""
    pid = get_service_pid()
    running = is_service_running()
    
    return {
        "running": running,
        "pid": pid,
        "port": 3456,
        "endpoint": "http://127.0.0.1:3456",
        "pid_file": str(PID_FILE),
        "reference_count": get_reference_count()
    }