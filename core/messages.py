# core/messages.py - Çok dilli mesaj sistemi
from typing import Dict, Any, Optional
from enum import Enum

class Language(str, Enum):
    TURKISH = "tr"
    ENGLISH = "en"
    SPANISH = "es"

class MessageType(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

class Messages:
    """Çok dilli mesaj sistemi"""
    
    MESSAGES = {
        # Genel mesajlar
        "welcome": {
            "tr": "Stüdyo Cepte API v2.0'a hoş geldiniz!",
            "en": "Welcome to Studio Cepte API v2.0!",
            "es": "¡Bienvenido a Studio Cepte API v2.0!"
        },
        "server_error": {
            "tr": "Beklenmeyen bir sunucu hatası oluştu",
            "en": "An unexpected server error occurred",
            "es": "Ocurrió un error inesperado del servidor"
        },
        "validation_error": {
            "tr": "Gönderilen veriler geçersiz",
            "en": "Invalid data provided",
            "es": "Datos inválidos proporcionados"
        },
        "not_found": {
            "tr": "İstenen kaynak bulunamadı",
            "en": "Requested resource not found",
            "es": "Recurso solicitado no encontrado"
        },
        "unauthorized": {
            "tr": "Bu işlem için yetkiniz bulunmuyor",
            "en": "You don't have permission for this operation",
            "es": "No tienes permiso para esta operación"
        },
        "rate_limit_exceeded": {
            "tr": "İstek limitini aştınız. Lütfen daha sonra tekrar deneyin",
            "en": "Rate limit exceeded. Please try again later",
            "es": "Límite de solicitudes excedido. Por favor, inténtelo más tarde"
        },
        "file_too_large": {
            "tr": "Dosya çok büyük. Maksimum boyut: {max_size}MB",
            "en": "File too large. Maximum size: {max_size}MB",
            "es": "Archivo demasiado grande. Tamaño máximo: {max_size}MB"
        },
        "invalid_file_type": {
            "tr": "Geçersiz dosya türü: {file_type}. İzin verilen türler: {allowed_types}",
            "en": "Invalid file type: {file_type}. Allowed types: {allowed_types}",
            "es": "Tipo de archivo inválido: {file_type}. Tipos permitidos: {allowed_types}"
        },
        
        # Auth mesajları
        "auth_token_invalid": {
            "tr": "Geçersiz veya süresi dolmuş kimlik doğrulama tokenı",
            "en": "Invalid or expired authentication token",
            "es": "Token de autenticación inválido o expirado"
        },
        "auth_token_missing": {
            "tr": "Kimlik doğrulama tokenı bulunamadı",
            "en": "Authentication token not found", 
            "es": "Token de autenticación no encontrado"
        },
        "email_already_exists": {
            "tr": "Bu e-posta adresi zaten kullanımda",
            "en": "This email address is already in use",
            "es": "Esta dirección de correo electrónico ya está en uso"
        },
        "invalid_credentials": {
            "tr": "Geçersiz e-posta veya şifre",
            "en": "Invalid email or password",
            "es": "Correo electrónico o contraseña inválidos"
        },
        "guest_cannot_login_password": {
            "tr": "Misafir hesapları şifre ile giriş yapamaz",
            "en": "Guest accounts cannot login with password",
            "es": "Las cuentas de invitado no pueden iniciar sesión con contraseña"
        },
        "user_not_found": {
            "tr": "Kullanıcı bulunamadı",
            "en": "User not found",
            "es": "Usuario no encontrado"
        },
        "guest_not_found": {
            "tr": "Misafir hesabı bulunamadı",
            "en": "Guest account not found",
            "es": "Cuenta de invitado no encontrada"
        },
        "invalid_guest_id": {
            "tr": "Geçersiz veya eksik misafir ID",
            "en": "Invalid or missing guest ID",
            "es": "ID de invitado inválido o faltante"
        },
        "not_guest_account": {
            "tr": "Bu hesap bir misafir hesabı değil",
            "en": "This account is not a guest account",
            "es": "Esta cuenta no es una cuenta de invitado"
        },
        "register_success": {
            "tr": "Kullanıcı başarıyla kaydedildi",
            "en": "User registered successfully",
            "es": "Usuario registrado exitosamente"
        },
        "login_success": {
            "tr": "Giriş başarılı",
            "en": "Login successful",
            "es": "Inicio de sesión exitoso"
        },
        "profile_updated": {
            "tr": "Profil başarıyla güncellendi",
            "en": "Profile updated successfully",
            "es": "Perfil actualizado exitosamente"
        },
        "guest_created": {
            "tr": "Misafir hesabı oluşturuldu",
            "en": "Guest account created",
            "es": "Cuenta de invitado creada"
        },
        
        # Image processing mesajları
        "no_files_provided": {
            "tr": "İşlenecek dosya bulunamadı",
            "en": "No files provided for processing",
            "es": "No se proporcionaron archivos para procesar"
        },
        "image_processing_started": {
            "tr": "Görüntü işleme başlatıldı",
            "en": "Image processing started",
            "es": "Procesamiento de imagen iniciado"
        },
        "image_processing_completed": {
            "tr": "Görüntü işleme tamamlandı",
            "en": "Image processing completed",
            "es": "Procesamiento de imagen completado"
        },
        "batch_processing_completed": {
            "tr": "Toplu işlem tamamlandı. Başarılı: {success_count}, Hatalı: {error_count}",
            "en": "Batch processing completed. Successful: {success_count}, Failed: {error_count}",
            "es": "Procesamiento por lotes completado. Exitosos: {success_count}, Fallidos: {error_count}"
        },
        "image_processing_error": {
            "tr": "Görüntü işlenirken hata oluştu: {error}",
            "en": "Error occurred while processing image: {error}",
            "es": "Error al procesar la imagen: {error}"
        },
        "file_processing_error": {
            "tr": "Dosya işlenirken hata oluştu: {filename}",
            "en": "Error processing file: {filename}",
            "es": "Error al procesar el archivo: {filename}"
        },
        
        # Security mesajları
        "suspicious_content_detected": {
            "tr": "Dosyada şüpheli içerik tespit edildi",
            "en": "Suspicious content detected in file",
            "es": "Contenido sospechoso detectado en el archivo"
        },
        "malicious_metadata_detected": {
            "tr": "Kötü amaçlı metadata tespit edildi",
            "en": "Malicious metadata detected",
            "es": "Metadatos maliciosos detectados"
        },
        "file_validation_failed": {
            "tr": "Dosya doğrulama başarısız",
            "en": "File validation failed",
            "es": "Falló la validación del archivo"
        },
        "invalid_image_file": {
            "tr": "Geçersiz veya bozuk görüntü dosyası",
            "en": "Invalid or corrupted image file",
            "es": "Archivo de imagen inválido o corrupto"
        },
        "input_too_long": {
            "tr": "Girdi çok uzun. Maksimum uzunluk: {max_length}",
            "en": "Input too long. Maximum length: {max_length}",
            "es": "Entrada demasiado larga. Longitud máxima: {max_length}"
        },
        "suspicious_input_detected": {
            "tr": "Girdide şüpheli içerik tespit edildi",
            "en": "Suspicious content detected in input",
            "es": "Contenido sospechoso detectado en la entrada"
        },
        "potential_sql_injection": {
            "tr": "Potansiyel SQL enjeksiyonu tespit edildi",
            "en": "Potential SQL injection detected",
            "es": "Posible inyección SQL detectada"
        },
        "ip_blocked": {
            "tr": "IP adresi şüpheli aktivite nedeniyle engellendi",
            "en": "IP address blocked due to suspicious activity",
            "es": "Dirección IP bloqueada por actividad sospechosa"
        },
        
        # Database mesajları
        "database_connection_error": {
            "tr": "Veritabanı bağlantı hatası",
            "en": "Database connection error",
            "es": "Error de conexión a la base de datos"
        },
        "database_operation_failed": {
            "tr": "Veritabanı işlemi başarısız",
            "en": "Database operation failed",
            "es": "Operación de base de datos falló"
        },
        
        # Health check mesajları
        "health_check_ok": {
            "tr": "Sistem sağlıklı",
            "en": "System healthy",
            "es": "Sistema saludable"
        },
        "health_check_degraded": {
            "tr": "Sistem kısmen çalışıyor",
            "en": "System partially operational",
            "es": "Sistema parcialmente operativo"
        },
        
        # additional_messages    

        "guest_user_name": {
            "tr": "Misafir Kullanıcı",
            "en": "Guest User", 
            "es": "Usuario Invitado"
        },
        "service_unavailable": {
            "tr": "Servis şu anda kullanılamıyor",
            "en": "Service currently unavailable",
            "es": "Servicio actualmente no disponible"
        },
        "processing_limit_exceeded": {
            "tr": "İşleme limiti aşıldı. Lütfen daha sonra tekrar deneyin",
            "en": "Processing limit exceeded. Please try again later",
            "es": "Límite de procesamiento excedido. Por favor, inténtelo más tarde"
        },
        "invalid_image_format": {
            "tr": "Geçersiz görüntü formatı. Desteklenen formatlar: PNG, JPG, WEBP",
            "en": "Invalid image format. Supported formats: PNG, JPG, WEBP", 
            "es": "Formato de imagen inválido. Formatos soportados: PNG, JPG, WEBP"
        },
        "image_too_large": {
            "tr": "Görüntü çok büyük. Maksimum boyut: {max_size}MB",
            "en": "Image too large. Maximum size: {max_size}MB",
            "es": "Imagen demasiado grande. Tamaño máximo: {max_size}MB"
        },
        "processing_failed": {
            "tr": "İşleme başarısız oldu",
            "en": "Processing failed",
            "es": "Procesamiento falló"
        },
        "batch_processing_started": {
            "tr": "Toplu işlem başlatıldı: {file_count} dosya",
            "en": "Batch processing started: {file_count} files",
            "es": "Procesamiento por lotes iniciado: {file_count} archivos"
        },
        "security_violation": {
            "tr": "Güvenlik ihlali tespit edildi",
            "en": "Security violation detected",
            "es": "Violación de seguridad detectada"
        },
        "maintenance_mode": {
            "tr": "Sistem bakımda. Lütfen daha sonra tekrar deneyin",
            "en": "System under maintenance. Please try again later",
            "es": "Sistema en mantenimiento. Por favor, inténtelo más tarde"
        }
    }
    
    @classmethod
    def get(cls, key: str, lang: str = "tr", **kwargs) -> str:
        """
        Belirtilen dilde mesaj döndürür
        
        Args:
            key: Mesaj anahtarı
            lang: Dil kodu (tr, en, es)
            **kwargs: Mesajda format edilecek parametreler
        
        Returns:
            str: Formatlanmış mesaj
        """
        if key not in cls.MESSAGES:
            return f"Message key '{key}' not found"
        
        lang_messages = cls.MESSAGES[key]
        if lang not in lang_messages:
            lang = "tr"  # Fallback to Turkish
        
        message = lang_messages[lang]
        
        try:
            return message.format(**kwargs)
        except KeyError as e:
            return f"Missing parameter {e} for message '{key}'"
    
    @classmethod 
    def get_available_languages(cls) -> list:
        """Mevcut dilleri döndürür"""
        return [lang.value for lang in Language]
    
    @classmethod
    def get_message_with_type(cls, key: str, message_type: MessageType, lang: str = "tr", **kwargs) -> Dict[str, Any]:
        """
        Mesajı tip bilgisi ile birlikte döndürür
        
        Returns:
            dict: {
                "message": "Mesaj içeriği",
                "type": "success|error|warning|info",
                "language": "tr|en|es"
            }
        """
        return {
            "message": cls.get(key, lang, **kwargs),
            "type": message_type.value,
            "language": lang
        }

# Convenience functions
def success_message(key: str, lang: str = "tr", **kwargs) -> Dict[str, Any]:
    return Messages.get_message_with_type(key, MessageType.SUCCESS, lang, **kwargs)

def error_message(key: str, lang: str = "tr", **kwargs) -> Dict[str, Any]:
    return Messages.get_message_with_type(key, MessageType.ERROR, lang, **kwargs)

def warning_message(key: str, lang: str = "tr", **kwargs) -> Dict[str, Any]:
    return Messages.get_message_with_type(key, MessageType.WARNING, lang, **kwargs)

def info_message(key: str, lang: str = "tr", **kwargs) -> Dict[str, Any]:
    return Messages.get_message_with_type(key, MessageType.INFO, lang, **kwargs)