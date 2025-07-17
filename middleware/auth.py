from typing import Any, Dict, Callable

def api_key_auth(config: Dict[str, Any]) -> Callable:
    """API key authentication middleware"""
    
    def auth_middleware(request, response, done: Callable):
        # Skip auth for health endpoints
        if request.url in ["/", "/health"]:
            return done()
        
        api_key = config.get("APIKEY")
        if not api_key:
            return done()
        
        # Get auth key from headers
        auth_key = request.headers.get("authorization") or request.headers.get("x-api-key")
        if not auth_key:
            response.status_code = 401
            response.body = "APIKEY is missing"
            return
        
        # Extract token
        token = ""
        if auth_key.startswith("Bearer"):
            token = auth_key.split(" ")[1]
        else:
            token = auth_key
        
        if token != api_key:
            response.status_code = 401
            response.body = "Invalid API key"
            return
        
        done()
    
    return auth_middleware