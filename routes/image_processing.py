# routes/image_processing.py - Güncellenmiş image processing routes
import io
import asyncio
from typing import List
import numpy as np
from fastapi import APIRouter, File, UploadFile, HTTPException, status, Request, Query, Depends
from fastapi.responses import JSONResponse
from rembg import remove, new_session
from PIL import Image
from skimage import morphology
from scipy.ndimage import gaussian_filter
from loguru import logger
import base64
import time

from core.logging_system import api_logger, ErrorHandler, log_and_handle_error, error_context, ErrorCategory, APIError
from core.messages import Messages
from core.dependencies import get_current_user
from core.models import UserData
from middleware.security import SecurityService

router = APIRouter()
REMBG_SESSION = new_session("isnet-general-use")
security_service = SecurityService()

def apply_mask_to_image(original_bytes: bytes, mask_image: Image.Image) -> bytes:
    """Orijinal görüntüye maske uygular"""
    try:
        input_image = Image.open(io.BytesIO(original_bytes))
        if input_image.mode != 'RGBA':
            input_image = input_image.convert('RGBA')
        
        alpha = mask_image.convert("L")
        input_image.putalpha(alpha)
        
        output_buffer = io.BytesIO()
        input_image.save(output_buffer, format="PNG")
        return output_buffer.getvalue()
    except Exception as e:
        logger.error(f"Error applying mask to image: {e}")
        raise

async def process_single_image(
    file: UploadFile, 
    request_id: str, 
    user_id: str = None
) -> bytes:
    """Tek bir görüntüyü işler"""
    try:
        logger.bind(request_id=request_id, user_id=user_id).info(f"Processing image: {file.filename}")
        
        # Dosya boyutu kontrolü
        file_content = await file.read()
        
        # Güvenlik kontrolü
        is_valid, validation_message = security_service.validate_file_security(file_content, file.filename)
        if not is_valid:
            logger.bind(request_id=request_id, user_id=user_id).warning(f"File validation failed: {validation_message}")
            raise ValueError(validation_message)
        
        # Ana işleme süreci
        start_time = time.time()
        
        # Body mask oluştur
        body_mask_bytes = remove(file_content, session=REMBG_SESSION, only_mask=True, alpha_matting=False)
        body_mask = Image.open(io.BytesIO(body_mask_bytes)).convert("L")

        # Detail mask oluştur (alpha matting ile)
        details_mask_bytes = remove(
            file_content, session=REMBG_SESSION, only_mask=True,
            alpha_matting=True, alpha_matting_foreground_threshold=200,
            alpha_matting_background_threshold=20, alpha_matting_erode_size=10
        )
        details_mask = Image.open(io.BytesIO(details_mask_bytes)).convert("L")
        
        # Maskeleri birleştir ve temizle
        body_array = np.array(body_mask) > 127
        details_array = np.array(details_mask) > 127
        combined_array = np.logical_or(body_array, details_array)
        
        # Morfological operations ile temizleme
        cleaned_array = morphology.remove_small_objects(combined_array, min_size=250)
        filled_array = morphology.remove_small_holes(cleaned_array, area_threshold=150)
        smoothed_array = gaussian_filter(filled_array.astype(float), sigma=1)
        final_mask = Image.fromarray((smoothed_array * 255).astype(np.uint8))
        
        # Final sonucu oluştur
        result = apply_mask_to_image(file_content, final_mask)
        
        processing_time = time.time() - start_time
        logger.bind(request_id=request_id, user_id=user_id).info(
            f"Image processed successfully: {file.filename} in {processing_time:.2f}s"
        )
        
        return result
        
    except Exception as e:
        logger.bind(request_id=request_id, user_id=user_id).error(f"Error processing image {file.filename}: {e}")
        raise

@router.post("/remove-background/single/")
@log_and_handle_error(
    category=ErrorCategory.IMAGE_PROCESSING,
    message_key="image_processing_error",
    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
)
async def remove_background_single(
    request: Request,
    file: UploadFile = File(...),
    current_user: UserData = Depends(get_current_user),
    lang: str = Query("tr", description="Language code (tr, en, es)")
):
    """
    Tek bir görüntünün arka planını kaldırır
    
    - **file**: İşlenecek görüntü dosyası (PNG, JPG, WEBP)
    - **lang**: Dil kodu (tr, en, es)
    """
    with error_context(ErrorCategory.IMAGE_PROCESSING, "single_image_processing", request, current_user.uid) as request_id:
        
        if not file:
            raise APIError(
                message_key="no_files_provided",
                status_code=status.HTTP_400_BAD_REQUEST,
                category=ErrorCategory.IMAGE_PROCESSING,
                lang=lang
            )
        
        try:
            # Rate limiting kontrolü
            if security_service.is_rate_limited(request, 'process'):
                api_logger.log_security_event(
                    event_type="rate_limit_exceeded",
                    request=request,
                    request_id=request_id,
                    user_id=current_user.uid
                )
                raise APIError(
                    message_key="rate_limit_exceeded",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    category=ErrorCategory.RATE_LIMIT,
                    lang=lang
                )
            
            logger.bind(request_id=request_id, user_id=current_user.uid).info(
                f"Single image processing started for user {current_user.uid}"
            )
            
            # Görüntüyü işle
            processed_bytes = await process_single_image(file, request_id, current_user.uid)
            encoded_string = base64.b64encode(processed_bytes).decode('utf-8')
            
            result = {
                "success": True,
                "message": Messages.get("image_processing_completed", lang),
                "data": {
                    "processed_image": encoded_string,
                    "filename": file.filename,
                    "format": "PNG"
                },
                "language": lang
            }
            
            logger.bind(request_id=request_id, user_id=current_user.uid).info(
                "Single image processing completed successfully"
            )
            
            return JSONResponse(content=result)
            
        except APIError:
            raise
        except Exception as e:
            api_logger.log_error(
                error=e,
                category=ErrorCategory.IMAGE_PROCESSING,
                request=request,
                request_id=request_id,
                user_id=current_user.uid,
                additional_context={
                    "operation": "single_image_processing",
                    "filename": file.filename if file else "unknown"
                }
            )
            raise APIError(
                message_key="image_processing_error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                category=ErrorCategory.IMAGE_PROCESSING,
                lang=lang,
                error=str(e)
            )

@router.post("/remove-background/batch/")
@log_and_handle_error(
    category=ErrorCategory.IMAGE_PROCESSING,
    message_key="image_processing_error",
    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
)
async def remove_background_batch(
    request: Request,
    files: List[UploadFile] = File(...),
    current_user: UserData = Depends(get_current_user),
    lang: str = Query("tr", description="Language code (tr, en, es)")
):
    """
    Birden fazla görüntünün arka planını kaldırır (toplu işlem)
    
    - **files**: İşlenecek görüntü dosyaları listesi
    - **lang**: Dil kodu (tr, en, es)
    """
    with error_context(ErrorCategory.IMAGE_PROCESSING, "batch_image_processing", request, current_user.uid) as request_id:
        
        if not files:
            raise APIError(
                message_key="no_files_provided",
                status_code=status.HTTP_400_BAD_REQUEST,
                category=ErrorCategory.IMAGE_PROCESSING,
                lang=lang
            )
        
        try:
            # Rate limiting kontrolü
            if security_service.is_rate_limited(request, 'process'):
                api_logger.log_security_event(
                    event_type="rate_limit_exceeded_batch",
                    request=request,
                    request_id=request_id,
                    user_id=current_user.uid,
                    details={"file_count": len(files)}
                )
                raise APIError(
                    message_key="rate_limit_exceeded",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    category=ErrorCategory.RATE_LIMIT,
                    lang=lang
                )
            
            logger.bind(request_id=request_id, user_id=current_user.uid).info(
                f"Batch image processing started: {len(files)} files for user {current_user.uid}"
            )
            
            results = {"success": {}, "errors": {}}
            start_time = time.time()

            async def process_and_store(file: UploadFile):
                try:
                    processed_bytes = await process_single_image(file, request_id, current_user.uid)
                    encoded_string = base64.b64encode(processed_bytes).decode('utf-8')
                    results["success"][file.filename] = {
                        "data": encoded_string,
                        "format": "PNG"
                    }
                except Exception as e:
                    error_msg = Messages.get("file_processing_error", lang, filename=file.filename)
                    results["errors"][file.filename] = {
                        "error": str(e),
                        "message": error_msg
                    }
                    
                    # Her dosya hatası için ayrı log
                    logger.bind(request_id=request_id, user_id=current_user.uid).error(
                        f"Error processing file {file.filename}: {e}"
                    )

            # Tüm dosyaları paralel işle
            await asyncio.gather(*(process_and_store(file) for file in files))
            
            processing_time = time.time() - start_time
            success_count = len(results["success"])
            error_count = len(results["errors"])
            
            # Sonuç mesajı
            result_message = Messages.get(
                "batch_processing_completed", 
                lang, 
                success_count=success_count,
                error_count=error_count
            )
            
            response_data = {
                "success": True,
                "message": result_message,
                "data": results,
                "statistics": {
                    "total_files": len(files),
                    "successful": success_count,
                    "failed": error_count,
                    "processing_time": round(processing_time, 2)
                },
                "language": lang
            }
            
            logger.bind(request_id=request_id, user_id=current_user.uid).info(
                f"Batch processing completed. Success: {success_count}, Errors: {error_count}, Time: {processing_time:.2f}s"
            )
            
            return JSONResponse(content=response_data)
            
        except APIError:
            raise
        except Exception as e:
            api_logger.log_error(
                error=e,
                category=ErrorCategory.IMAGE_PROCESSING,
                request=request,
                request_id=request_id,
                user_id=current_user.uid,
                additional_context={
                    "operation": "batch_image_processing",
                    "file_count": len(files) if files else 0
                }
            )
            raise APIError(
                message_key="image_processing_error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                category=ErrorCategory.IMAGE_PROCESSING,
                lang=lang,
                error=str(e)
            )

@router.get("/health")
async def image_processing_health_check(
    request: Request,
    lang: str = Query("tr", description="Language code (tr, en, es)")
):
    """
    Image processing servisinin sağlık kontrolü
    
    - **lang**: Dil kodu (tr, en, es)
    """
    with error_context(ErrorCategory.SYSTEM, "health_check", request) as request_id:
        try:
            # REMBG session kontrolü
            test_health = REMBG_SESSION is not None
            
            health_status = {
                "service": "image_processing",
                "status": "healthy" if test_health else "unhealthy",
                "rembg_session": "ok" if test_health else "error",
                "message": Messages.get("health_check_ok" if test_health else "health_check_degraded", lang),
                "timestamp": time.time(),
                "language": lang
            }
            
            status_code = 200 if test_health else 503
            
            logger.bind(request_id=request_id).info(f"Image processing health check: {health_status['status']}")
            
            return JSONResponse(content=health_status, status_code=status_code)
            
        except Exception as e:
            api_logger.log_error(
                error=e,
                category=ErrorCategory.SYSTEM,
                request=request,
                request_id=request_id,
                additional_context={"operation": "health_check"}
            )
            
            error_response = {
                "service": "image_processing",
                "status": "error",
                "message": Messages.get("server_error", lang),
                "error": str(e),
                "timestamp": time.time(),
                "language": lang
            }
            
            return JSONResponse(content=error_response, status_code=503)