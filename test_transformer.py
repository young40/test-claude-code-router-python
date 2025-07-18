#!/usr/bin/env python3
"""
Test script for the transformer service to ensure it's working correctly.
"""

import asyncio
import json
import sys
from typing import Dict, Any, List, Optional
from pyllms.src.services.config import ConfigService, ConfigOptions
from pyllms.src.services.transformer import TransformerService
from pyllms.src.types.transformer import Transformer

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

async def test_transformer_service() -> bool:
    """Test the transformer service"""
    print_header("Testing Transformer Service")
    
    # Create config service
    config_service = ConfigService(ConfigOptions())
    
    # Create transformer service
    transformer_service = TransformerService(config_service)
    
    # Initialize transformer service
    print_info("Initializing transformer service...")
    await transformer_service.initialize()
    
    # Get all transformers
    transformers = transformer_service.get_all_transformers()
    print_info(f"Found {len(transformers)} transformers")
    
    # Check if we have the expected transformers
    expected_transformers = [
        "OpenAI", "Anthropic", "Gemini", "Groq", "DeepSeek", "OpenRouter", "maxtoken", "tooluse"
    ]
    
    found_transformers = []
    for name, transformer in transformers.items():
        found_transformers.append(name)
        print_info(f"Found transformer: {name}")
    
    # Check for missing transformers
    missing_transformers = [t for t in expected_transformers if t not in found_transformers]
    if missing_transformers:
        print_warning(f"Missing transformers: {', '.join(missing_transformers)}")
    else:
        print_success("All expected transformers found")
    
    # Get transformers with endpoints
    transformers_with_endpoint = transformer_service.get_transformers_with_endpoint()
    print_info(f"Found {len(transformers_with_endpoint)} transformers with endpoints")
    
    for item in transformers_with_endpoint:
        name = item["name"]
        transformer = item["transformer"]
        endpoint = transformer.end_point if hasattr(transformer, "end_point") else None
        print_info(f"Transformer with endpoint: {name} -> {endpoint}")
    
    # Check if we have the expected endpoints
    expected_endpoints = [
        "/v1/chat/completions",  # OpenAI
        "/v1/messages",          # Anthropic
        "/v1beta/models/gemini-pro:generateContent"  # Gemini
    ]
    
    found_endpoints = []
    for item in transformers_with_endpoint:
        transformer = item["transformer"]
        if hasattr(transformer, "end_point") and transformer.end_point:
            found_endpoints.append(transformer.end_point)
    
    # Check for missing endpoints
    missing_endpoints = [e for e in expected_endpoints if e not in found_endpoints]
    if missing_endpoints:
        print_warning(f"Missing endpoints: {', '.join(missing_endpoints)}")
    else:
        print_success("All expected endpoints found")
    
    return len(missing_transformers) == 0 and len(missing_endpoints) == 0

async def main() -> int:
    """Main function"""
    success = await test_transformer_service()
    
    if success:
        print_header("All Tests Passed")
        return 0
    else:
        print_header("Some Tests Failed")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))