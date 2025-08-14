# core/logging_system.py - Gelişmiş logging ve hata yönetimi
import json
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, Union
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from loguru import logger
import uuid
from contextlib import contextmanager
from functools import wraps

from core.messages import Messages, MessageType, Language

class LogLevel:
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class ErrorCategory:
    AUTH = "AUTH"
    VALIDATION = "VALIDATION"
    DATABASE = "DATABASE"
    SECURITY = "SECURITY"
    IMAGE_PROCESSING = "IMAGE_PROCESSING"
    RATE_LIMIT = "RATE_LIMIT"
    SYSTEM = "SYSTEM"
    NETWORK = "NETWORK"

class APILogger:
    """API için özelleştirilmiş logger sınıfı"""
    
    def __init__(self):
        self.setup_logger()
    
    def setup_logger(self):
        """Logger yapılandırması"""
        logger.remove()  # Varsayılan logger'ı kaldır
        
        # Console logger
        logger.add(
            sink=lambda msg: print(msg, end=""),
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level="INFO"
        )
        
        # File logger - General
        logger.add(
            "logs/app_{time:YYYY-MM-DD}.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {extra.get('request_id', 'no-id')} | {message}",
            level="INFO",
            rotation="00:00",
            retention="30 days",
            compression="zip",
            serialize=False
        )
        
        # File logger - Errors only
        logger.add(
            "logs/errors_{time:YYYY-MM-DD}.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {extra.get('request_id', 'no-id')} | {extra.get('user_id', 'no-user')} | {extra.get('error_category', 'no-category')} | {message}",
            level="ERROR",
            rotation="00:00",
            retention="90 days",
            compression="zip",
            serialize=True
        )
        
        # File logger - Security events
        logger.add(
            "logs/security_{time:YYYY-MM-DD}.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra.get('client_ip', 'no-ip')} | {extra.get('user_agent', 'no-agent')} | {extra.get('request_id', 'no-id')} | {extra.get('user_id', 'no-user')} | {message}",
            level="WARNING",
            rotation="00:00",
            retention="365 days",
            compression="zip",
            serialize=True,
            filter=lambda record: record["extra"].get("security_event", False)
        )
    
    def get_client_info(self, request: Request) -> Dict[str, str]:
        """İstek bilgilerini çıkarır"""
        return {
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("user-agent", "unknown"),
            "method": request.method,
            "path": str(request.url.path),
            "query_params": str(request.query_params)
        }
    
    def _get_client_ip(self, request: Request) -> str:
        """Gerçek client IP'sini döndürür"""
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else '127.0.0.1'
    
    def log_request(self, request: Request, request_id: str, user_id: Optional[str] = None):
        """İstek loglaması"""
        client_info = self.get_client_info(request)
        
        logger.bind(
            request_id=request_id,
            user_id=user_id or "anonymous",
            **client_info
        ).info(f"Request started: {request.method} {request.url.path}")
    
    def log_response(self, request: Request, request_id: str, status_code: int, response_time: float, user_id: Optional[str] = None):
        """Yanıt loglaması"""
        logger.bind(
            request_id=request_id,
            user_id=user_id or "anonymous",
            status_code=status_code,
            response_time=response_time
        ).info(f"Request completed: {request.method} {request.url.path} - {status_code} - {response_time:.3f}s")
    
    def log_error(
        self, 
        error: Exception, 
        category: str,
        request: Optional[Request] = None,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ):
        """Hata loglaması"""
        error_context = {
            "request_id": request_id or str(uuid.uuid4()),
            "user_id": user_id or "anonymous",
            "error_category": category,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc()
        }
        
        if request:
            error_context.update(self.get_client_info(request))
        
        if additional_context:
            error_context.update(additional_context)
        
        logger.bind(**error_context).error(f"Error in {category}: {str(error)}")
    
    def log_security_event(
        self,
        event_type: str,
        request: Request,
        request_id: str,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Güvenlik olayı loglaması"""
        client_info = self.get_client_info(request)
        
        security_context = {
            "request_id": request_id,
            "user_id": user_id or "anonymous",
            "security_event": True,
            "event_type": event_type,
            **client_info
        }
        
        if details:
            security_context.update(details)
        
        logger.bind(**security_context).warning(f"Security event: {event_type}")
    
    def log_auth_event(
        self,
        event_type: str,
        request: Request,
        request_id: str,
        user_id: Optional[str] = None,
        email: Optional[str] = None,
        success: bool = True
    ):
        """Kimlik doğrulama olayı loglaması"""
        auth_context = {
            "request_id": request_id,
            "user_id": user_id or "anonymous",
            "email": email or "unknown",
            "auth_event": True,
            "auth_success": success,
            **self.get_client_info(request)
        }
        
        level = "info" if success else "warning"
        getattr(logger.bind(**auth_context), level)(f"Auth event: {event_type}")

# Global logger instance
api_logger = APILogger()

class APIError(HTTPException):
    """Özelleştirilmiş API hata sınıfı"""
    
    def __init__(
        self,
        message_key: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        category: str = ErrorCategory.SYSTEM,
        lang: str = "tr",
        details: Optional[Dict[str, Any]] = None,
        **message_params
    ):
        self.message_key = message_key
        self.category = category
        self.lang = lang
        self.message_params = message_params
        self.details = details or {}
        
        # Mesajı al
        detail = Messages.get(message_key, lang, **message_params)
        
        super().__init__(status_code=status_code, detail=detail)

class ErrorHandler:
    """Merkezi hata yönetim sınıfı"""
    
    @staticmethod
    def create_error_response(
        message_key: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        lang: str = "tr",
        error_id: Optional[str] = None,
        **message_params
    ) -> JSONResponse:
        """Hata yanıtı oluşturur"""
        error_response = {
            "success": False,
            "error": {
                "message": Messages.get(message_key, lang, **message_params),
                "code": message_key,
                "language": lang,
                "timestamp": datetime.utcnow().isoformat(),
                "error_id": error_id or str(uuid.uuid4())
            }
        }
        
        return JSONResponse(
            status_code=status_code,
            content=error_response
        )
    
    @staticmethod
    def create_success_response(
        message_key: str,
        data: Optional[Dict[str, Any]] = None,
        lang: str = "tr",
        **message_params
    ) -> Dict[str, Any]:
        """Başarı yanıtı oluşturur"""
        response = {
            "success": True,
            "message": Messages.get(message_key, lang, **message_params),
            "language": lang,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if data:
            response["data"] = data
        
        return response

def log_and_handle_error(
    category: str = ErrorCategory.SYSTEM,
    message_key: str = "server_error",
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
):
    """Decorator for error logging and handling"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request_id = str(uuid.uuid4())
            request = None
            user_id = None
            lang = "tr"
            
            # Request ve user bilgilerini bul
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    lang = arg.query_params.get("lang", "tr")
                elif hasattr(arg, 'uid'):  # UserData object
                    user_id = arg.uid
            
            try:
                if request:
                    api_logger.log_request(request, request_id, user_id)
                
                result = await func(*args, **kwargs)
                
                if request:
                    api_logger.log_response(request, request_id, 200, 0.0, user_id)
                
                return result
                
            except HTTPException:
                raise  # HTTPException'ları yeniden fırlat
            except Exception as e:
                # Hata logla
                api_logger.log_error(
                    error=e,
                    category=category,
                    request=request,
                    request_id=request_id,
                    user_id=user_id,
                    additional_context={"function": func.__name__}
                )
                
                # Hata yanıtı döndür
                raise APIError(
                    message_key=message_key,
                    status_code=status_code,
                    category=category,
                    lang=lang
                )
        return wrapper
    return decorator

@contextmanager
def error_context(
    category: str,
    operation: str,
    request: Optional[Request] = None,
    user_id: Optional[str] = None
):
    """Context manager for error handling"""
    request_id = str(uuid.uuid4())
    
    try:
        if request:
            api_logger.log_request(request, request_id, user_id)
        
        logger.bind(request_id=request_id, user_id=user_id or "anonymous").info(f"Starting {operation}")
        yield request_id
        logger.bind(request_id=request_id, user_id=user_id or "anonymous").info(f"Completed {operation}")
        
    except Exception as e:
        api_logger.log_error(
            error=e,
            category=category,
            request=request,
            request_id=request_id,
            user_id=user_id,
            additional_context={"operation": operation}
        )
        raise