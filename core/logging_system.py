# core/logging_system.py - Fixed logging system
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
    """API için minimal logger sınıfı - sadece ERROR seviyesi"""
    
    def __init__(self):
        self.setup_logger()
    
    def setup_logger(self):
        """Minimal logger yapılandırması - sadece ERROR seviyesi"""
        logger.remove()  # Varsayılan logger'ı kaldır
        
        # Console logger - sadece ERROR seviyesi
        logger.add(
            sink=lambda msg: print(msg, end=""),
            format="<red>{time:YYYY-MM-DD HH:mm:ss}</red> | <level>{level: <8}</level> | <red>{message}</red>",
            level="ERROR"
        )
        
        # File logger - sadece ERROR seviyesi - FİX: Doğru format
        logger.add(
            "logs/errors_{time:YYYY-MM-DD}.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {extra[request_id]} | {extra[user_id]} | {extra[error_category]} | {message}",
            level="ERROR",
            rotation="00:00",
            retention="30 days",
            compression="zip",
            serialize=True,
            filter=self._error_filter
        )
    
    def _error_filter(self, record):
        """Error filter for ensuring required extra fields exist"""
        # Varsayılan değerleri ayarla
        if 'request_id' not in record['extra']:
            record['extra']['request_id'] = 'no-id'
        if 'user_id' not in record['extra']:
            record['extra']['user_id'] = 'no-user'
        if 'error_category' not in record['extra']:
            record['extra']['error_category'] = 'no-category'
        return True
    
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
        """İstek loglaması - devre dışı (sadece ERROR seviyesi)"""
        pass  # INFO seviyesi olduğu için log yazılmayacak
    
    def log_response(self, request: Request, request_id: str, status_code: int, response_time: float, user_id: Optional[str] = None):
        """Yanıt loglaması - devre dışı (sadece ERROR seviyesi)"""
        pass  # INFO seviyesi olduğu için log yazılmayacak
    
    def log_error(
        self, 
        error: Exception, 
        category: str,
        request: Optional[Request] = None,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ):
        """Hata loglaması - sadece bu fonksiyon çalışacak"""
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
        """Güvenlik olayı loglaması - sadece ciddi güvenlik ihlalleri"""
        client_info = self.get_client_info(request)
        
        security_context = {
            "request_id": request_id,
            "user_id": user_id or "anonymous",
            "error_category": "SECURITY",  # security_event yerine error_category
            "security_event": True,
            "event_type": event_type,
            **client_info
        }
        
        if details:
            security_context.update(details)
        
        # Sadece kritik güvenlik olayları için ERROR seviyesinde log
        if event_type in ["rate_limit_exceeded", "suspicious_activity", "blocked_ip"]:
            logger.bind(**security_context).error(f"Security violation: {event_type}")
    
    def log_auth_event(
        self,
        event_type: str,
        request: Request,
        request_id: str,
        user_id: Optional[str] = None,
        email: Optional[str] = None,
        success: bool = True
    ):
        """Kimlik doğrulama olayı loglaması - sadece başarısız girişler"""
        if not success:  # Sadece başarısız auth olayları
            auth_context = {
                "request_id": request_id,
                "user_id": user_id or "anonymous",
                "error_category": "AUTH",  # auth_event yerine error_category
                "email": email or "unknown",
                "auth_event": True,
                "auth_success": success,
                **self.get_client_info(request)
            }
            
            logger.bind(**auth_context).error(f"Auth failed: {event_type}")

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
                # Request loglaması devre dışı (INFO seviyesi)
                result = await func(*args, **kwargs)
                # Response loglaması devre dışı (INFO seviyesi)
                return result
                
            except HTTPException:
                raise  # HTTPException'ları yeniden fırlat
            except Exception as e:
                # Sadece ERROR seviyesi - bu çalışacak
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
        # Request loglaması devre dışı (INFO seviyesi)
        # Operation başlangıç loglaması devre dışı (INFO seviyesi)
        yield request_id
        # Operation tamamlanma loglaması devre dışı (INFO seviyesi)
        
    except Exception as e:
        # Sadece ERROR seviyesi - bu çalışacak
        api_logger.log_error(
            error=e,
            category=category,
            request=request,
            request_id=request_id,
            user_id=user_id,
            additional_context={"operation": operation}
        )
        raise