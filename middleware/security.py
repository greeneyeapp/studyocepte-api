from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import time
import hashlib
import magic
from typing import Dict, Optional
from collections import defaultdict, deque
from datetime import datetime, timedelta
import re
import os
from loguru import logger

# Rate limiting storage
rate_limit_storage: Dict[str, deque] = defaultdict(deque)
failed_attempts: Dict[str, list] = defaultdict(list)

class SecurityService:
    """Comprehensive security service for API protection."""
    
    def __init__(self):
        self.max_file_size = 50 * 1024 * 1024  # 50MB
        self.allowed_image_types = {
            'image/jpeg', 'image/png', 'image/webp', 'image/bmp', 'image/tiff'
        }
        # GÜNCELLENEN RATE LIMIT DEĞERLERİ - Önceki değerler çok düşüktü
        self.max_requests_per_minute = {
            'upload': 50,      # 10'dan 50'ye çıkarıldı
            'process': 30,     # 5'ten 30'a çıkarıldı  
            'list': 200,       # 60'tan 200'e çıkarıldı
            'detail': 120      # 30'dan 120'ye çıkarıldı
        }
        self.blocked_ips = set()
        self.suspicious_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'data:text/html',
            r'vbscript:',
            r'onload\s*=',
            r'onerror\s*='
        ]
    
    def get_client_ip(self, request: Request) -> str:
        """Get real client IP address."""
        # Check for forwarded headers (when behind proxy/CDN)
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else '127.0.0.1'
    
    def is_rate_limited(self, request: Request, endpoint_type: str) -> bool:
        """Check if request should be rate limited."""
        client_ip = self.get_client_ip(request)
        
        # Check if IP is blocked
        if client_ip in self.blocked_ips:
            return True
        
        current_time = time.time()
        limit = self.max_requests_per_minute.get(endpoint_type, 100)  # Default limit da artırıldı
        
        # Clean old entries (older than 1 minute)
        while (rate_limit_storage[client_ip] and 
               current_time - rate_limit_storage[client_ip][0] > 60):
            rate_limit_storage[client_ip].popleft()
        
        # Check if limit exceeded
        if len(rate_limit_storage[client_ip]) >= limit:
            # Log suspicious activity
            logger.warning(f"Rate limit exceeded for IP {client_ip} on {endpoint_type}")
            self._record_failed_attempt(client_ip, 'rate_limit')
            return True
        
        # Add current request
        rate_limit_storage[client_ip].append(current_time)
        return False
    
    def _record_failed_attempt(self, client_ip: str, reason: str):
        """Record failed attempt and block IP if necessary."""
        current_time = datetime.now()
        failed_attempts[client_ip].append({
            'timestamp': current_time,
            'reason': reason
        })
        
        # Clean old attempts (older than 1 hour)
        failed_attempts[client_ip] = [
            attempt for attempt in failed_attempts[client_ip]
            if current_time - attempt['timestamp'] < timedelta(hours=1)
        ]
        
        # IP engelleme eşiği de artırıldı (20'den 50'ye)
        if len(failed_attempts[client_ip]) > 50:
            self.blocked_ips.add(client_ip)
            logger.error(f"IP {client_ip} blocked due to suspicious activity")
    
    def validate_file_security(self, file_content: bytes, filename: str) -> tuple[bool, str]:
        """Comprehensive file security validation."""
        try:
            # Size check
            if len(file_content) > self.max_file_size:
                return False, f"File too large. Maximum size: {self.max_file_size / (1024*1024)}MB"
            
            # MIME type check using python-magic
            try:
                mime_type = magic.from_buffer(file_content, mime=True)
            except Exception:
                # Fallback to basic checks
                mime_type = self._guess_mime_type(filename)
            
            if mime_type not in self.allowed_image_types:
                return False, f"Invalid file type: {mime_type}. Allowed: {', '.join(self.allowed_image_types)}"
            
            # Check for embedded scripts in image files - SADELEŞTIRILDI
            if self._contains_suspicious_content(file_content):
                return False, "Suspicious content detected in file"
            
            # Check file headers for image files
            if not self._validate_image_headers(file_content, mime_type):
                return False, "Invalid or corrupted image file"
            
            # Metadata kontrolü sadeleştirildi ve daha tolerant hale getirildi
            if self._contains_dangerous_metadata(file_content):
                return False, "Potentially dangerous content detected"
            
            return True, "File validation passed"
            
        except Exception as e:
            logger.error(f"File validation error: {e}")
            return False, "File validation failed"
    
    def _contains_suspicious_content(self, file_content: bytes) -> bool:
        """Check for suspicious scripts in file content - more lenient"""
        try:
            # Sadece ilk 5KB'ı kontrol et ve daha spesifik pattern'ler kullan
            content_str = file_content[:5120].decode('utf-8', errors='ignore').lower()
            
            # Sadece gerçekten tehlikeli pattern'leri ara
            dangerous_patterns = [
                '<script',
                'javascript:',
                'vbscript:',
                'data:text/html',
                'eval(',
                'exec(',
                'system('
            ]
            
            for pattern in dangerous_patterns:
                if pattern in content_str:
                    logger.warning(f"Suspicious pattern found: {pattern}")
                    return True
            
            return False
        except:
            # Decode hatası durumunda güvenli kabul et
            return False
    
    def _guess_mime_type(self, filename: str) -> str:
        """Fallback MIME type detection."""
        ext = os.path.splitext(filename)[1].lower()
        mime_map = {
            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.png': 'image/png', '.webp': 'image/webp',
            '.bmp': 'image/bmp', '.tiff': 'image/tiff', '.tif': 'image/tiff'
        }
        return mime_map.get(ext, 'application/octet-stream')
    
    def _validate_image_headers(self, file_content: bytes, mime_type: str) -> bool:
        """Validate image file headers."""
        if len(file_content) < 10:
            return False
        
        # Check common image signatures
        signatures = {
            'image/jpeg': [b'\xFF\xD8\xFF'],
            'image/png': [b'\x89PNG\r\n\x1a\n'],
            'image/webp': [b'RIFF'],  # WEBP kontrol sadeleştirildi
            'image/bmp': [b'BM'],
            'image/tiff': [b'II*\x00', b'MM\x00*']
        }
        
        expected_sigs = signatures.get(mime_type, [])
        
        # Eğer signature check tanımlı değilse veya eşleşiyorsa geçerli
        if not expected_sigs:
            return True
            
        for sig in expected_sigs:
            if file_content.startswith(sig):
                return True
        
        # WEBP için özel kontrol
        if mime_type == 'image/webp':
            if file_content.startswith(b'RIFF') and b'WEBP' in file_content[:20]:
                return True
        
        return False
    
    def _contains_dangerous_metadata(self, file_content: bytes) -> bool:
        """Check for dangerous metadata - MUCH MORE LENIENT"""
        try:
            # Sadece gerçekten tehlikeli executable content'i ara
            dangerous_strings = [
                b'<?php',
                b'<script>',
                b'javascript:',
                b'vbscript:',
                b'data:text/html'
            ]
            
            # Sadece dosyanın ilk 10KB'ında ara
            content_to_check = file_content[:10240]
            
            for dangerous in dangerous_strings:
                if dangerous in content_to_check:
                    logger.warning(f"Dangerous content found: {dangerous}")
                    return True
            
            return False
        except:
            # Hata durumunda güvenli kabul et
            return False
    
    def validate_input_data(self, data: str, max_length: int = 1000) -> tuple[bool, str]:
        """Validate input data for XSS and injection attacks."""
        if len(data) > max_length:
            return False, f"Input too long. Maximum length: {max_length}"
        
        # Check for XSS patterns
        for pattern in self.suspicious_patterns:
            if re.search(pattern, data, re.IGNORECASE):
                return False, "Suspicious content detected in input"
        
        # Check for SQL injection patterns
        sql_patterns = [
            r"union\s+select", r"drop\s+table", r"delete\s+from",
            r"insert\s+into", r"update\s+set", r"--\s", r"/\*.*\*/"
        ]
        
        for pattern in sql_patterns:
            if re.search(pattern, data, re.IGNORECASE):
                return False, "Potential SQL injection detected"
        
        return True, "Input validation passed"
    
    def generate_csrf_token(self, user_id: str) -> str:
        """Generate CSRF token for user."""
        timestamp = str(int(time.time()))
        data = f"{user_id}:{timestamp}:csrf_secret"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def validate_csrf_token(self, token: str, user_id: str) -> bool:
        """Validate CSRF token."""
        try:
            # Token should be valid for 1 hour
            current_time = int(time.time())
            
            for i in range(3600):  # Check last hour
                timestamp = str(current_time - i)
                expected_data = f"{user_id}:{timestamp}:csrf_secret"
                expected_token = hashlib.sha256(expected_data.encode()).hexdigest()
                
                if token == expected_token:
                    return True
            
            return False
        except Exception:
            return False

# Global security service
security_service = SecurityService()