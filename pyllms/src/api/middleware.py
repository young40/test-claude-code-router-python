from typing import Dict, Any, Optional, Callable
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import traceback

from ..utils.log import log


class ApiError(Exception):
    """API Error class"""
    
    def __init__(
        self, 
        message: str, 
        status_code: int = 500, 
        code: str = "internal_error", 
        error_type: str = "api_error"
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.error_type = error_type


def create_api_error(
    message: str, 
    status_code: int = 500, 
    code: str = "internal_error", 
    error_type: str = "api_error"
) -> ApiError:
    """Create an API error"""
    return ApiError(message, status_code, code, error_type)


async def error_handler(error: Exception, request: Request) -> JSONResponse:
    """Error handler middleware"""
    # Log the error
    log(f"Error: {error}")
    log(traceback.format_exc())
    
    # Determine status code and error response
    if isinstance(error, ApiError):
        status_code = error.status_code
        response = {
            "error": {
                "message": str(error),
                "type": error.error_type,
                "code": error.code
            }
        }
    elif isinstance(error, HTTPException):
        status_code = error.status_code
        response = {
            "error": {
                "message": error.detail,
                "type": "api_error",
                "code": "http_error"
            }
        }
    elif isinstance(error, RequestValidationError):
        status_code = 400
        response = {
            "error": {
                "message": "Validation error",
                "type": "validation_error",
                "code": "invalid_request",
                "details": error.errors()
            }
        }
    else:
        status_code = 500
        # Include more detailed error information for debugging
        response = {
            "error": {
                "message": str(error) or "Internal Server Error",
                "type": "api_error",
                "code": "internal_error"
            }
        }
    
    # Ensure consistent error response format with TypeScript implementation
    return JSONResponse(status_code=status_code, content=response)


def setup_error_handlers(app):
    """Setup error handlers for the FastAPI application"""
    
    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, error: ApiError):
        return await error_handler(error, request)
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, error: HTTPException):
        return await error_handler(error, request)
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, error: RequestValidationError):
        return await error_handler(error, request)
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, error: Exception):
        return await error_handler(error, request)