#!/usr/bin/env python3
"""
Test script to verify feature parity between TypeScript and Python implementations.
This script tests endpoints and providers to ensure consistent behavior.
"""

import asyncio
import json
import httpx
import argparse
import sys
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

# Configuration
TS_BASE_URL = "http://localhost:3000"  # TypeScript server URL
PY_BASE_URL = "http://localhost:3001"  # Python server URL

# Test data
TEST_PROVIDERS = [
    {
        "name": "test-openai",
        "base_url": "https://api.openai.com",
        "api_key": "sk-test-key",
        "models": ["gpt-3.5-turbo", "gpt-4"]
    },
    {
        "name": "test-anthropic",
        "base_url": "https://api.anthropic.com",
        "api_key": "sk-test-key",
        "models": ["claude-3-opus", "claude-3-sonnet"]
    },
    {
        "name": "test-gemini",
        "base_url": "https://generativelanguage.googleapis.com",
        "api_key": "test-key",
        "models": ["gemini-pro", "gemini-ultra"]
    },
    {
        "name": "test-groq",
        "base_url": "https://api.groq.com",
        "api_key": "test-key",
        "models": ["llama3-8b", "mixtral-8x7b"]
    },
    {
        "name": "test-deepseek",
        "base_url": "https://api.deepseek.com",
        "api_key": "test-key",
        "models": ["deepseek-coder", "deepseek-chat"]
    },
    {
        "name": "test-openrouter",
        "base_url": "https://openrouter.ai/api",
        "api_key": "test-key",
        "models": ["openrouter/auto", "openrouter/mistral"]
    }
]

# Test requests for each provider
TEST_REQUESTS = {
    "openai": {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "user", "content": "Hello, how are you?"}
        ],
        "temperature": 0.7,
        "max_tokens": 100
    },
    "anthropic": {
        "model": "claude-3-sonnet",
        "messages": [
            {"role": "user", "content": "Hello, how are you?"}
        ],
        "temperature": 0.7,
        "max_tokens": 100
    },
    "gemini": {
        "model": "gemini-pro",
        "messages": [
            {"role": "user", "content": "Hello, how are you?"}
        ],
        "temperature": 0.7,
        "max_tokens": 100
    },
    "groq": {
        "model": "llama3-8b",
        "messages": [
            {"role": "user", "content": "Hello, how are you?"}
        ],
        "temperature": 0.7,
        "max_tokens": 100
    },
    "deepseek": {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": "Hello, how are you?"}
        ],
        "temperature": 0.7,
        "max_tokens": 100
    },
    "openrouter": {
        "model": "openrouter/auto",
        "messages": [
            {"role": "user", "content": "Hello, how are you?"}
        ],
        "temperature": 0.7,
        "max_tokens": 100
    }
}

# Test requests for utility transformers
UTILITY_TEST_REQUESTS = {
    "maxtoken": {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": "Write a very long response about the history of AI"}
        ],
        "temperature": 0.7,
        "max_tokens": 50  # Deliberately small to test maxtoken transformer
    },
    "tooluse": {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": "What's the weather like today?"}
        ],
        "temperature": 0.7,
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get the current weather for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "The location to get weather for"
                            }
                        },
                        "required": ["location"]
                    }
                }
            }
        ]
    }
}

# Colors for terminal output
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

async def check_server_health(client: httpx.AsyncClient, base_url: str, server_name: str) -> bool:
    """Check if a server is healthy"""
    try:
        response = await client.get(f"{base_url}/health", timeout=5.0)
        if response.status_code == 200:
            data = response.json()
            print_success(f"{server_name} server is healthy: {data}")
            return True
        else:
            print_error(f"{server_name} server returned status code {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Failed to connect to {server_name} server: {e}")
        return False

async def register_test_provider(client: httpx.AsyncClient, base_url: str, provider: Dict[str, Any]) -> bool:
    """Register a test provider with the server"""
    try:
        response = await client.post(
            f"{base_url}/providers",
            json={
                "id": provider["name"],
                "name": provider["name"],
                "type": provider["name"].split("-")[1] if "-" in provider["name"] else "custom",
                "baseUrl": provider["base_url"],
                "apiKey": provider["api_key"],
                "models": provider["models"],
                "enabled": True
            }
        )
        
        if response.status_code in (200, 201):
            print_success(f"Registered provider {provider['name']}")
            return True
        else:
            # If provider already exists, that's fine
            if response.status_code == 400 and "already exists" in response.text:
                print_info(f"Provider {provider['name']} already exists")
                return True
            print_warning(f"Failed to register provider {provider['name']}: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print_error(f"Error registering provider {provider['name']}: {e}")
        return False

async def test_endpoint(
    client: httpx.AsyncClient, 
    base_url: str, 
    endpoint: str, 
    request_data: Dict[str, Any],
    provider_name: str
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Test an endpoint with a request"""
    try:
        # Add provider to model field
        if "model" in request_data:
            request_data["model"] = f"{provider_name},{request_data['model']}"
        
        response = await client.post(
            f"{base_url}{endpoint}",
            json=request_data,
            timeout=10.0
        )
        
        if response.status_code == 200:
            return True, response.json()
        else:
            print_warning(f"Endpoint {endpoint} returned status code {response.status_code}: {response.text}")
            return False, None
    except Exception as e:
        print_error(f"Error testing endpoint {endpoint}: {e}")
        return False, None

async def compare_responses(ts_response: Dict[str, Any], py_response: Dict[str, Any]) -> bool:
    """Compare responses from TypeScript and Python implementations"""
    # Check if both responses have the same structure
    if set(ts_response.keys()) != set(py_response.keys()):
        print_warning(f"Response keys differ: TS {set(ts_response.keys())} vs PY {set(py_response.keys())}")
        return False
    
    # For this test, we're not comparing the actual content since we're using mock providers
    # Instead, we're checking that the structure is the same
    return True

async def run_tests(ts_url: str, py_url: str) -> None:
    """Run all tests"""
    async with httpx.AsyncClient() as client:
        # Check server health
        ts_healthy = await check_server_health(client, ts_url, "TypeScript")
        py_healthy = await check_server_health(client, py_url, "Python")
        
        if not ts_healthy or not py_healthy:
            print_error("One or both servers are not healthy. Aborting tests.")
            return
        
        # Register test providers
        print_header("Registering Test Providers")
        for provider in TEST_PROVIDERS:
            ts_registered = await register_test_provider(client, ts_url, provider)
            py_registered = await register_test_provider(client, py_url, provider)
            
            if not ts_registered or not py_registered:
                print_warning(f"Failed to register provider {provider['name']} on one or both servers")
        
        # Test provider-specific endpoints
        print_header("Testing Provider-Specific Endpoints")
        
        # Test OpenAI endpoint
        print_info("Testing OpenAI endpoint (/v1/chat/completions)")
        ts_success, ts_response = await test_endpoint(
            client, ts_url, "/v1/chat/completions", 
            TEST_REQUESTS["openai"], "test-openai"
        )
        py_success, py_response = await test_endpoint(
            client, py_url, "/v1/chat/completions", 
            TEST_REQUESTS["openai"], "test-openai"
        )
        
        if ts_success and py_success:
            if await compare_responses(ts_response, py_response):
                print_success("OpenAI endpoint responses match")
            else:
                print_warning("OpenAI endpoint responses have different structures")
        else:
            print_error("Failed to test OpenAI endpoint on one or both servers")
        
        # Test Anthropic endpoint
        print_info("Testing Anthropic endpoint (/v1/messages)")
        ts_success, ts_response = await test_endpoint(
            client, ts_url, "/v1/messages", 
            TEST_REQUESTS["anthropic"], "test-anthropic"
        )
        py_success, py_response = await test_endpoint(
            client, py_url, "/v1/messages", 
            TEST_REQUESTS["anthropic"], "test-anthropic"
        )
        
        if ts_success and py_success:
            if await compare_responses(ts_response, py_response):
                print_success("Anthropic endpoint responses match")
            else:
                print_warning("Anthropic endpoint responses have different structures")
        else:
            print_error("Failed to test Anthropic endpoint on one or both servers")
        
        # Test Gemini endpoint
        print_info("Testing Gemini endpoint (/v1beta/models/gemini-pro:generateContent)")
        ts_success, ts_response = await test_endpoint(
            client, ts_url, "/v1beta/models/gemini-pro:generateContent", 
            TEST_REQUESTS["gemini"], "test-gemini"
        )
        py_success, py_response = await test_endpoint(
            client, py_url, "/v1beta/models/gemini-pro:generateContent", 
            TEST_REQUESTS["gemini"], "test-gemini"
        )
        
        if ts_success and py_success:
            if await compare_responses(ts_response, py_response):
                print_success("Gemini endpoint responses match")
            else:
                print_warning("Gemini endpoint responses have different structures")
        else:
            print_error("Failed to test Gemini endpoint on one or both servers")
        
        # Test utility transformers
        print_header("Testing Utility Transformers")
        
        # Test MaxToken transformer
        print_info("Testing MaxToken transformer")
        ts_success, ts_response = await test_endpoint(
            client, ts_url, "/v1/chat/completions", 
            UTILITY_TEST_REQUESTS["maxtoken"], "test-openai"
        )
        py_success, py_response = await test_endpoint(
            client, py_url, "/v1/chat/completions", 
            UTILITY_TEST_REQUESTS["maxtoken"], "test-openai"
        )
        
        if ts_success and py_success:
            if await compare_responses(ts_response, py_response):
                print_success("MaxToken transformer responses match")
            else:
                print_warning("MaxToken transformer responses have different structures")
        else:
            print_error("Failed to test MaxToken transformer on one or both servers")
        
        # Test ToolUse transformer
        print_info("Testing ToolUse transformer")
        ts_success, ts_response = await test_endpoint(
            client, ts_url, "/v1/chat/completions", 
            UTILITY_TEST_REQUESTS["tooluse"], "test-openai"
        )
        py_success, py_response = await test_endpoint(
            client, py_url, "/v1/chat/completions", 
            UTILITY_TEST_REQUESTS["tooluse"], "test-openai"
        )
        
        if ts_success and py_success:
            if await compare_responses(ts_response, py_response):
                print_success("ToolUse transformer responses match")
            else:
                print_warning("ToolUse transformer responses have different structures")
        else:
            print_error("Failed to test ToolUse transformer on one or both servers")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Test feature parity between TypeScript and Python implementations")
    parser.add_argument("--ts-url", default=TS_BASE_URL, help="TypeScript server URL")
    parser.add_argument("--py-url", default=PY_BASE_URL, help="Python server URL")
    args = parser.parse_args()
    
    print_header("Feature Parity Test")
    print_info(f"TypeScript server: {args.ts_url}")
    print_info(f"Python server: {args.py_url}")
    print_info(f"Test started at: {datetime.now().isoformat()}")
    
    asyncio.run(run_tests(args.ts_url, args.py_url))
    
    print_header("Test Completed")

if __name__ == "__main__":
    main()