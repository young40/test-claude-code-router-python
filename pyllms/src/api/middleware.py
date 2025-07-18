from typing import Dict, Any, Optional
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
import traceback

from ..utils.log import log


class ApiError(Exception):
    """API错误类"""
    
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
    """创建API错误"""
    return ApiError(message, status_code, code, error_type)


async def error_handler(error: Exception, request: Request) -> JSONResponse:
    """错误处理器"""
    # 记录错误
    log(f"Error: {error}")
    log(traceback.format_exc())
    
    # 确定状态码和错误信息
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
    else:
        status_code = 500
        response = {
            "error": {
                "message": "Internal Server Error",
                "type": "api_error",
                "code": "internal_error"
            }
        }
    
    return JSONResponse(status_code=status_code, content=response)