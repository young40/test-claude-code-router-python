import json
from typing import Any, Dict, List, Union

try:
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
except ImportError:
    # Fallback if tiktoken is not available
    class MockEncoder:
        def encode(self, text: str) -> List[int]:
            # Rough approximation: 1 token ≈ 4 characters
            return [0] * (len(text) // 4)
    enc = MockEncoder()

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.log import log

def get_use_model(request: Any, token_count: int, config: Dict[str, Any]) -> str:
    """Determine which model to use based on request and token count"""
    model = request.get("model", "")
    
    if "," in model:
        return model
    
    # If token count is greater than 60K, use the long context model
    if token_count > 60000 and config.get("Router", {}).get("longContext"):
        log("Using long context model due to token count:", token_count)
        return config["Router"]["longContext"]
    
    # If the model is claude-3-5-haiku, use the background model
    if model.startswith("claude-3-5-haiku") and config.get("Router", {}).get("background"):
        log("Using background model for", model)
        return config["Router"]["background"]
    
    # If exists thinking, use the think model
    if request.get("thinking") and config.get("Router", {}).get("think"):
        log("Using think model for", request.get("thinking"))
        return config["Router"]["think"]
    
    return config.get("Router", {}).get("default", "")

def count_tokens_in_content(content: Union[str, List[Dict[str, Any]]]) -> int:
    """Count tokens in message content"""
    token_count = 0
    
    if isinstance(content, str):
        token_count += len(enc.encode(content))
    elif isinstance(content, list):
        for content_part in content:
            if content_part.get("type") == "text":
                token_count += len(enc.encode(content_part.get("text", "")))
            elif content_part.get("type") == "tool_use":
                token_count += len(enc.encode(json.dumps(content_part.get("input", {}))))
            elif content_part.get("type") == "tool_result":
                content_data = content_part.get("content", "")
                if isinstance(content_data, str):
                    token_count += len(enc.encode(content_data))
                else:
                    token_count += len(enc.encode(json.dumps(content_data)))
    
    return token_count

async def router(request: Any, response: Any, config: Dict[str, Any]):
    """Router middleware to select appropriate model"""
    try:
        messages = request.get("messages", [])
        system = request.get("system", [])
        tools = request.get("tools", [])
        
        token_count = 0
        
        # Count tokens in messages
        if isinstance(messages, list):
            for message in messages:
                content = message.get("content", "")
                token_count += count_tokens_in_content(content)
        
        # Count tokens in system messages
        if isinstance(system, str):
            token_count += len(enc.encode(system))
        elif isinstance(system, list):
            for item in system:
                if item.get("type") == "text":
                    text = item.get("text", "")
                    if isinstance(text, str):
                        token_count += len(enc.encode(text))
                    elif isinstance(text, list):
                        for text_part in text:
                            token_count += len(enc.encode(text_part or ""))
        
        # Count tokens in tools
        if tools:
            for tool in tools:
                if tool.get("description"):
                    token_count += len(enc.encode(tool.get("name", "") + tool.get("description", "")))
                if tool.get("input_schema"):
                    token_count += len(enc.encode(json.dumps(tool.get("input_schema"))))
        
        model = get_use_model(request, token_count, config)
        request["model"] = model
        
    except Exception as error:
        log("Error in router middleware:", str(error))
        request["model"] = config.get("Router", {}).get("default", "")