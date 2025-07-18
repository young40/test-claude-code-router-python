#!/usr/bin/env python3
"""
Script to run both TypeScript and Python servers for feature parity testing.
"""

import os
import sys
import subprocess
import time
import argparse
import signal
import atexit
import requests
from typing import List, Optional

# Default ports
TS_PORT = 3000
PY_PORT = 3001

# Global variables to track processes
ts_process = None
py_process = None

def start_ts_server(port: int) -> subprocess.Popen:
    """Start the TypeScript server"""
    print(f"Starting TypeScript server on port {port}...")
    env = os.environ.copy()
    env["PORT"] = str(port)
    
    # Change to the llms directory
    os.chdir("llms")
    
    # Start the server
    process = subprocess.Popen(
        ["npm", "run", "dev"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Change back to the original directory
    os.chdir("..")
    
    return process

def start_py_server(port: int) -> subprocess.Popen:
    """Start the Python server"""
    print(f"Starting Python server on port {port}...")
    env = os.environ.copy()
    env["PORT"] = str(port)
    
    # Start the server
    process = subprocess.Popen(
        ["python", "-m", "pyllms.main"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    return process

def wait_for_server(url: str, max_retries: int = 30, retry_interval: int = 1) -> bool:
    """Wait for a server to become available"""
    print(f"Waiting for server at {url}...")
    for i in range(max_retries):
        try:
            response = requests.get(f"{url}/health", timeout=1)
            if response.status_code == 200:
                print(f"Server at {url} is ready!")
                return True
        except requests.RequestException:
            pass
        
        time.sleep(retry_interval)
        sys.stdout.write(".")
        sys.stdout.flush()
    
    print(f"\nServer at {url} did not become available after {max_retries} retries")
    return False

def cleanup() -> None:
    """Clean up processes on exit"""
    if ts_process:
        print("Stopping TypeScript server...")
        ts_process.terminate()
        try:
            ts_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            ts_process.kill()
    
    if py_process:
        print("Stopping Python server...")
        py_process.terminate()
        try:
            py_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            py_process.kill()

def run_test(ts_url: str, py_url: str) -> int:
    """Run the feature parity test"""
    print("Running feature parity test...")
    result = subprocess.run(
        ["python", "test_feature_parity.py", "--ts-url", ts_url, "--py-url", py_url],
        capture_output=False
    )
    return result.returncode

def main() -> int:
    """Main function"""
    parser = argparse.ArgumentParser(description="Run feature parity tests")
    parser.add_argument("--ts-port", type=int, default=TS_PORT, help="TypeScript server port")
    parser.add_argument("--py-port", type=int, default=PY_PORT, help="Python server port")
    parser.add_argument("--skip-ts", action="store_true", help="Skip starting TypeScript server")
    parser.add_argument("--skip-py", action="store_true", help="Skip starting Python server")
    args = parser.parse_args()
    
    # Register cleanup handler
    atexit.register(cleanup)
    signal.signal(signal.SIGINT, lambda sig, frame: sys.exit(1))
    
    ts_url = f"http://localhost:{args.ts_port}"
    py_url = f"http://localhost:{args.py_port}"
    
    global ts_process, py_process
    
    # Start TypeScript server if not skipped
    if not args.skip_ts:
        ts_process = start_ts_server(args.ts_port)
        if not wait_for_server(ts_url):
            print("Failed to start TypeScript server")
            return 1
    
    # Start Python server if not skipped
    if not args.skip_py:
        py_process = start_py_server(args.py_port)
        if not wait_for_server(py_url):
            print("Failed to start Python server")
            return 1
    
    # Run the test
    return run_test(ts_url, py_url)

if __name__ == "__main__":
    sys.exit(main())