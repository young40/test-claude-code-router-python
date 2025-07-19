from typing import Dict, List, Any, Optional, AsyncIterable
from fastapi import FastAPI, Request, Response, Depends, HTTPException, Body
from fastapi.responses import JSONResponse, StreamingResponse
import httpx
from datetime import datetime
import json
import asyncio

from ..types.llm import UnifiedChatRequest, RegisterProviderRequest, LLMProvider
from ..utils.request import send_unified_request
from ..utils.log import log
from .middleware import create_api_error


def register_api_routes(app: FastAPI) -> None:
    """Register API routes"""
    
    # Health check and info endpoints
    @app.get("/")
    async def root():
        return {"message": "LLMs API", "version": "1.0.0"}
    
    @app.get("/health")
    async def health():
        return {"status": "ok", "timestamp": datetime.now().isoformat()}
    
    # Get transformers with endpoints
    transformers_with_endpoint = app.state._server.transformer_service.get_transformers_with_endpoint()
    log(f"Available transformers: {[item['name'] for item in transformers_with_endpoint]}")
    
    # Register specific routes for each transformer with an endpoint
    for item in transformers_with_endpoint:
        name = item["name"]
        transformer = item["transformer"]
        
        if hasattr(transformer, 'end_point') and transformer.end_point:
            endpoint = transformer.end_point
            if not isinstance(endpoint, str):
                endpoint = f"/{name.lower()}"
            log(f"Registering endpoint for transformer {name}: {endpoint}")
            
            # Use a factory function to ensure each route handler has the correct transformer reference
            def create_endpoint_handler(transformer_instance=transformer):
                async def handle_endpoint(request: Request):
                    log(f"Processing {endpoint} request using transformer: {transformer_instance.name if hasattr(transformer_instance, 'name') else 'unknown'}")
                    return await process_transformer_request(request, transformer_instance)
                return handle_endpoint
            
            # Register the endpoint
            endpoint_handler = create_endpoint_handler()
            app.add_api_route(
                endpoint, 
                endpoint_handler, 
                methods=["POST"]
            )
    
    # Add a wildcard route as fallback to catch all unmatched requests
    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
    async def catch_all(request: Request, path: str):
        log(f"Caught unmatched request: {request.method} {request.url}")
        log(f"Path: {path}")
        
        # Try to find a matching transformer
        transformers_with_endpoint = app.state._server.transformer_service.get_transformers_with_endpoint()
        
        # Keep track of registered endpoints to avoid duplicates
        registered_endpoints = set()
        for route in app.routes:
            if hasattr(route, "path"):
                registered_endpoints.add(route.path.lstrip('/'))
        
        for item in transformers_with_endpoint:
            transformer = item["transformer"]
            if hasattr(transformer, 'end_point'):
                # Remove leading slash for comparison
                endpoint = transformer.end_point.lstrip('/')
                request_path = path.lstrip('/')
                
                # Only process if this endpoint wasn't explicitly registered
                if endpoint not in registered_endpoints and (request_path == endpoint or request_path.startswith(f"{endpoint}/")):
                    log(f"Found matching transformer in wildcard route: {item['name']}")
                    return await process_transformer_request(request, transformer)
        
        # Return 404 error using consistent error format
        log(f"No matching route found: {path}")
        raise create_api_error(
            f"Not Found: {path}",
            404,
            "route_not_found",
            "api_error"
        )
    
    # Process transformer request
    async def process_transformer_request(request: Request, transformer):
        log(f"Processing transformer request: URL={request.url}, Transformer={transformer.name if hasattr(transformer, 'name') else 'unknown'}")
        try:
            body = await request.json()
            log(f"Request body: {json.dumps(body, ensure_ascii=False)}")
            
            provider_name = getattr(request.state, "provider", None)
            log(f"Provider name: {provider_name}")
            
            if not provider_name:
                # Get provider from request if available
                if "provider" in body:
                    provider_name = body["provider"]
                    log(f"Using provider from request: {provider_name}")
                else:
                    # Default provider as fallback
                    provider_name = "default"
                    log(f"Using default provider: {provider_name}")
            
            provider = app.state._server.provider_service.get_provider(provider_name)
            log(f"Retrieved provider: {provider}")
            
            if not provider:
                log(f"Provider not found: {provider_name}")
                raise create_api_error(
                    f"Provider '{provider_name}' not found",
                    404,
                    "provider_not_found"
                )
            
            # Initialize request body and config
            request_body = body
            config = {}
            
            # Transform request using transformer's transformRequestOut
            log("Starting request transformation (transformRequestOut)")
            if hasattr(transformer, 'transform_request_out') and callable(transformer.transform_request_out):
                log("Calling transform_request_out")
                transform_out = await transformer.transform_request_out(body)
                
                # Handle different return types from transformRequestOut
                if hasattr(transform_out, 'body') and transform_out.body is not None:
                    request_body = transform_out.body
                    config = transform_out.config or {}
                    log(f"Transformed request body: {json.dumps(request_body, ensure_ascii=False) if isinstance(request_body, dict) else str(request_body)}")
                else:
                    request_body = transform_out
                    log(f"Transformed request body: {json.dumps(request_body, ensure_ascii=False) if isinstance(request_body, dict) else str(request_body)}")
            
            # Apply provider transformers (transformRequestIn)
            transformer_dict = getattr(provider, 'transformer', {}) or {}
            log('Provider transformers:', transformer_dict.get('use', []))
            if transformer_dict.get('use'):
                for t in transformer_dict['use']:
                    if not t or not hasattr(t, 'transform_request_in') or not callable(t.transform_request_in):
                        log(f"Skipping transformer without transform_request_in method")
                        continue
                    
                    log(f"Applying provider transformer: {t.name if hasattr(t, 'name') else 'unknown'}")
                    transform_in = await t.transform_request_in(request_body, provider)
                    
                    # Handle different return types from transformRequestIn
                    if hasattr(transform_in, 'body') and transform_in.body is not None:
                        request_body = transform_in.body
                        config = {**config, **(transform_in.config or {})}
                    else:
                        request_body = transform_in
            
            # Apply model-specific transformers if available
            model_name = body.get('model')
            model_transformers = transformer_dict.get(model_name, {}).get('use', []) if model_name else []
            if model_name and model_transformers:
                for t in model_transformers:
                    if not t or not hasattr(t, 'transform_request_in') or not callable(t.transform_request_in):
                        continue
                    
                    log(f"Applying model transformer: {t.name if hasattr(t, 'name') else 'unknown'}")
                    transform_result = await t.transform_request_in(request_body, provider)
                    
                    # Handle different return types
                    if hasattr(transform_result, 'body') and transform_result.body is not None:
                        request_body = transform_result.body
                        config = {**config, **(transform_result.config or {})}
                    else:
                        request_body = transform_result
            
            # Send request to provider
            url = config.get('url') or provider.base_url
            log(f"Sending request to: {url}")
            
            # Prepare request configuration
            request_config = {
                'https_proxy': app.state._server.config_service.get_https_proxy(),
                **config,
                'headers': {
                    'Authorization': f"Bearer {provider.api_key}",
                    **(config.get('headers') or {})
                }
            }
            
            # Send the request
            response = await send_unified_request(url, request_body, request_config)
            
            # Handle error responses
            if isinstance(response, str):
                error_text = response
                log(f"Error response: {error_text}")
                raise create_api_error(
                    f"Error from provider: {error_text}",
                    500,
                    "provider_error"
                )
            if response.status_code != 200:
                if hasattr(response, "aiter_text") and callable(response.aiter_text):
                    error_text = ""
                    async for chunk in response.aiter_text():
                        error_text += chunk
                elif hasattr(response, "text") and isinstance(response.text, str):
                    error_text = response.text
                else:
                    error_text = str(response)
                log(f"Error response from {url}: {error_text}")
                raise create_api_error(
                    f"Error from provider: {error_text}",
                    response.status_code,
                    "provider_response_error"
                )
            
            # Process response
            final_response = response
            
            # Apply provider transformers for response (transformResponseOut)
            if provider.get('transformer', {}).get('use'):
                for t in provider['transformer']['use']:
                    if not t or not hasattr(t, 'transform_response_out') or not callable(t.transform_response_out):
                        log(f"Skipping transformer without transform_response_out method")
                        continue
                    
                    log(f"Applying provider response transformer: {t.name if hasattr(t, 'name') else 'unknown'}")
                    try:
                        final_response = await t.transform_response_out(final_response)
                    except Exception as e:
                        log(f"Error in transform_response_out: {e}")
                        # Continue with other transformers even if one fails
            
            # Apply model-specific transformers for response if available
            if model_name and provider.get('transformer', {}).get(model_name, {}).get('use'):
                for t in provider['transformer'][model_name]['use']:
                    if not t or not hasattr(t, 'transform_response_out') or not callable(t.transform_response_out):
                        continue
                    
                    log(f"Applying model response transformer: {t.name if hasattr(t, 'name') else 'unknown'}")
                    try:
                        final_response = await t.transform_response_out(final_response)
                    except Exception as e:
                        log(f"Error in model-specific transform_response_out: {e}")
                        # Continue with other transformers even if one fails
            
            # Apply transformer's transformResponseIn
            if hasattr(transformer, 'transform_response_in') and callable(transformer.transform_response_in):
                log(f"Applying transformer response_in: {transformer.name if hasattr(transformer, 'name') else 'unknown'}")
                try:
                    final_response = await transformer.transform_response_in(final_response)
                except Exception as e:
                    log(f"Error in transform_response_in: {e}")
                    # If the final transformer fails, we still need to return something
            
            # Return appropriate response based on status code
            if final_response.status_code != 200:
                return Response(
                    content=await final_response.read(),
                    status_code=final_response.status_code,
                    headers=dict(final_response.headers)
                )
            
            # Handle streaming vs. non-streaming responses
            is_stream = body.get('stream', False)
            if is_stream:
                # For streaming responses, we need to ensure proper SSE format
                # This matches the TypeScript implementation which returns the response body directly
                log("Returning streaming response")
                
                # Create a streaming response that properly forwards the stream
                return StreamingResponse(
                    content=final_response.aiter_bytes(),
                    status_code=final_response.status_code,
                    media_type="text/event-stream",
                    headers={
                        "Content-Type": "text/event-stream",
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive"
                    }
                )
            else:
                # For regular responses, return the JSON content
                # This matches the TypeScript implementation which returns the JSON response
                try:
                    # Read the response content
                    response_content = await final_response.read()
                    
                    # Try to parse as JSON to validate it (but don't modify the content)
                    try:
                        json.loads(response_content)
                        log("Returning valid JSON response")
                    except json.JSONDecodeError:
                        log("Response is not valid JSON, returning as raw content")
                    
                    # Return the original content regardless of JSON validity
                    # This ensures we don't modify the response content
                    return Response(
                        content=response_content,
                        media_type=final_response.headers.get("content-type", "application/json"),
                        status_code=final_response.status_code
                    )
                except Exception as e:
                    log(f"Error processing response: {e}")
                    # If there's an error reading the response, return an error
                    raise create_api_error(
                        f"Error processing provider response: {str(e)}",
                        500,
                        "response_processing_error"
                    )
        except Exception as e:
            log(f"Error processing request: {e}")
            # Use the create_api_error function to ensure consistent error format
            raise create_api_error(
                f"Error processing request: {str(e)}",
                500,
                "request_processing_error",
                "api_error"
            )
    
    # 提供者管理端点
    @app.post("/providers")
    async def create_provider(request: RegisterProviderRequest):
        # 验证
        if not request.name or not request.name.strip():
            raise create_api_error("Provider name is required", 400, "invalid_request")
        
        if not request.base_url or not is_valid_url(request.base_url):
            raise create_api_error("Valid base URL is required", 400, "invalid_request")
        
        if not request.api_key or not request.api_key.strip():
            raise create_api_error("API key is required", 400, "invalid_request")
        
        if not request.models or len(request.models) == 0:
            raise create_api_error("At least one model is required", 400, "invalid_request")
        
        # 检查提供者是否已存在
        if app.state._server.provider_service.get_provider(request.name):
            raise create_api_error(
                f"Provider with name '{request.name}' already exists",
                400,
                "provider_exists"
            )
        
        provider = app.state._server.provider_service.register_provider(request)
        return provider
    
    @app.get("/providers")
    async def get_providers():
        return app.state._server.provider_service.get_providers()
    
    @app.get("/providers/{id}")
    async def get_provider(id: str):
        provider = app.state._server.provider_service.get_provider(id)
        if not provider:
            raise create_api_error(
                f"Provider '{id}' not found",
                404,
                "provider_not_found"
            )
        return provider
    
    @app.put("/providers/{id}")
    async def update_provider(id: str, updates: Dict[str, Any]):
        provider = app.state._server.provider_service.update_provider(id, updates)
        if not provider:
            raise create_api_error(
                f"Provider '{id}' not found",
                404,
                "provider_not_found"
            )
        return provider
    
    @app.delete("/providers/{id}")
    async def delete_provider(id: str):
        success = app.state._server.provider_service.delete_provider(id)
        if not success:
            raise create_api_error(
                f"Provider '{id}' not found",
                404,
                "provider_not_found"
            )
        return {"message": "Provider deleted successfully"}
    
    @app.patch("/providers/{id}/toggle")
    async def toggle_provider(id: str, body: Dict[str, bool]):
        enabled = body.get("enabled", False)
        success = app.state._server.provider_service.toggle_provider(id, enabled)
        if not success:
            raise create_api_error(
                f"Provider '{id}' not found",
                404,
                "provider_not_found"
            )
        return {
            "message": f"Provider {'enabled' if enabled else 'disabled'} successfully"
        }


def is_valid_url(url: str) -> bool:
    """检查URL是否有效"""
    try:
        httpx.URL(url)
        return True
    except:
        return False