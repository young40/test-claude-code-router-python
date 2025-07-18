#!/usr/bin/env python3
"""
Test script for the server to ensure it's working correctly.
"""

import asyncio
import json
import sys
import httpx
import argparse
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

# Default server URL
SERVER_URL = "http://localhost:3001"

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text: str) -> None:
    """Print a header with formatting"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(80)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}\n")

def print_success(text: str) -> None:
    """Print a success message"""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")

def print_warning(text: str) -> None:
    """Print a warning message"""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")

def print_error(text: str) -> None:
    """Print an error message"""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")

def print_info(text: str) -> None:
    """Print an info message"""
    print(f"{Colors.OKBLUE}ℹ {text}{Colors.ENDC}")

async def check_server_health(client: httpx.AsyncClient, base_url: str) -> bool:
    """Check if the server is healthy"""
    try:
        response = await client.get(f"{base_url}/health", timeout=5.0)
        if response.status_code == 200:
            data = response.json()
            print_success(f"Server is healthy: {data}")
            return True
        else:
            print_error(f"Server returned status code {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Failed to connect to server: {e}")
        return False

async def test_root_endpoint(client: httpx.AsyncClient, base_url: str) -> bool:
    """Test the root endpoint"""
    try:
        response = await client.get(f"{base_url}/", timeout=5.0)
        if response.status_code == 200:
            data = response.json()
            print_success(f"Root endpoint returned: {data}")
            return True
        else:
            print_error(f"Root endpoint returned status code {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Failed to connect to root endpoint: {e}")
        return False

async def register_test_provider(client: httpx.AsyncClient, base_url: str) -> bool:
    """Register a test provider with the server"""
    try:
        provider = {
            "id": "test-provider",
            "name": "test-provider",
            "type": "openai",
            "baseUrl": "https://api.openai.com",
            "apiKey": "sk-test-key",
            "models": ["gpt-3.5-turbo", "gpt-4"],
            "enabled": True
        }
        
        response = await client.post(f"{base_url}/providers", json=provider)
        
        if response.status_code in (200, 201):
            print_success(f"Registered test provider")
            return True
        else:
            # If provider already exists, that's fine
            if response.status_code == 400 and "already exists" in response.text:
                print_info(f"Test provider already exists")
                return True
            print_warning(f"Failed to register test provider: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print_error(f"Error registering test provider: {e}")
        return False

async def test_get_providers(client: httpx.AsyncClient, base_url: str) -> bool:
    """Test getting providers"""
    try:
        response = await client.get(f"{base_url}/providers", timeout=5.0)
        if response.status_code == 200:
            data = response.json()
            print_success(f"Got providers: {len(data)} providers found")
            return True
        else:
            print_error(f"Get providers returned status code {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Failed to get providers: {e}")
        return False

async def test_get_provider(client: httpx.AsyncClient, base_url: str) -> bool:
    """Test getting a specific provider"""
    try:
        response = await client.get(f"{base_url}/providers/test-provider", timeout=5.0)
        if response.status_code == 200:
            data = response.json()
            print_success(f"Got provider: {data.get('name')}")
            return True
        else:
            print_error(f"Get provider returned status code {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Failed to get provider: {e}")
        return False

async def test_update_provider(client: httpx.AsyncClient, base_url: str) -> bool:
    """Test updating a provider"""
    try:
        updates = {
            "models": ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"]
        }
        
        response = await client.put(f"{base_url}/providers/test-provider", json=updates)
        
        if response.status_code == 200:
            data = response.json()
            print_success(f"Updated provider: {data.get('name')}")
            return True
        else:
            print_error(f"Update provider returned status code {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Failed to update provider: {e}")
        return False

async def test_toggle_provider(client: httpx.AsyncClient, base_url: str) -> bool:
    """Test toggling a provider"""
    try:
        # Disable provider
        response = await client.patch(f"{base_url}/providers/test-provider/toggle", json={"enabled": False})
        
        if response.status_code != 200:
            print_error(f"Toggle provider (disable) returned status code {response.status_code}")
            return False
        
        # Enable provider
        response = await client.patch(f"{base_url}/providers/test-provider/toggle", json={"enabled": True})
        
        if response.status_code == 200:
            print_success(f"Successfully toggled provider")
            return True
        else:
            print_error(f"Toggle provider (enable) returned status code {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Failed to toggle provider: {e}")
        return False

async def run_tests(base_url: str) -> bool:
    """Run all tests"""
    async with httpx.AsyncClient() as client:
        # Check server health
        if not await check_server_health(client, base_url):
            return False
        
        # Test root endpoint
        if not await test_root_endpoint(client, base_url):
            return False
        
        # Register test provider
        if not await register_test_provider(client, base_url):
            return False
        
        # Test getting providers
        if not await test_get_providers(client, base_url):
            return False
        
        # Test getting a specific provider
        if not await test_get_provider(client, base_url):
            return False
        
        # Test updating a provider
        if not await test_update_provider(client, base_url):
            return False
        
        # Test toggling a provider
        if not await test_toggle_provider(client, base_url):
            return False
        
        return True

def main() -> int:
    """Main function"""
    parser = argparse.ArgumentParser(description="Test the server")
    parser.add_argument("--url", default=SERVER_URL, help="Server URL")
    args = parser.parse_args()
    
    print_header("Server Test")
    print_info(f"Server URL: {args.url}")
    print_info(f"Test started at: {datetime.now().isoformat()}")
    
    success = asyncio.run(run_tests(args.url))
    
    if success:
        print_header("All Tests Passed")
        return 0
    else:
        print_header("Some Tests Failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())