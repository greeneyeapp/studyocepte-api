import io 
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, status, Depends
from loguru import logger
from firebase_admin import firestore
# PIL ve numpy artık apply_filters_to_photo kaldırıldığı için doğrudan burada kullanılmayacak
# from PIL import Image, ImageEnhance, ImageFilter
# import numpy as np

from core.firebase_config import db
from core.storage_config import storage_client
from core.models import UserData, ProductPhotoBase, EditorSettingsRequest 
from core.dependencies import get_current_user
from core.config import settings

router = APIRouter()

def get_signed_url(gcs_path: str) -> str:
    """Generate signed URL for GCS path."""
    # Eğer path zaten bir HTTP/HTTPS URL ise, tekrar imzalamaya çalışma
    if gcs_path and (gcs_path.startswith('http://') or gcs_path.startswith('https://')):
        return gcs_path

    if not gcs_path or not gcs_path.startswith(f"gs://{settings.STORAGE_BUCKET_NAME}/"):
        logger.warning(f"Geçersiz GCS yolu formatı veya boş: {gcs_path}")
        return ""
    try:
        blob_path = gcs_path.replace(f"gs://{settings.STORAGE_BUCKET_NAME}/", "")
        bucket = storage_client.bucket(settings.STORAGE_BUCKET_NAME)
        blob = bucket.blob(blob_path)
        signed_url = blob.generate_signed_url(
            version="v4", 
            expiration=timedelta(minutes=15), 
            method="GET"
        )
        logger.info(f"GCS yolu '{gcs_path}' için imzalı URL oluşturuldu: {signed_url}")
        return signed_url
    except Exception as e:
        logger.warning(f"İmzalı URL hatası ({gcs_path}): {e}")
        return ""

@router.get("/{photo_id}", response_model=ProductPhotoBase)
async def get_photo_by_id(
    photo_id: str,
    current_user: UserData = Depends(get_current_user)
):
    """Get a specific photo by ID."""
    try:
        products_ref = db.collection('products').where('userId', '==', current_user.uid).stream()
        
        for product_doc in products_ref:
            photo_ref = product_doc.reference.collection('photos').document(photo_id)
            photo_doc_result = photo_ref.get()
            
            if photo_doc_result.exists:
                photo_data = photo_doc_result.to_dict()
                photo_data['id'] = photo_doc_result.id
                
                # Generate signed URLs for all relevant image URLs
                photo_data['thumbnailUrl'] = get_signed_url(photo_data.get('thumbnailUrl', ''))
                photo_data['processedImageUrl'] = get_signed_url(photo_data.get('processedImageUrl', ''))
                # rawImageUrl artık client'a gönderilmeyecek, bu satır kaldırıldı
                # photo_data['rawImageUrl'] = get_signed_url(photo_data.get('rawImageUrl', ''))
                
                return ProductPhotoBase.model_validate(photo_data)
        
        logger.warning(f"Fotoğraf bulunamadı: {photo_id}")
        raise HTTPException(status_code=404, detail="Fotoğraf bulunamadı.")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fotoğraf detayı çekilirken hata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Fotoğraf detayı alınırken bir hata oluştu.")

@router.put("/{photo_id}/settings", status_code=status.HTTP_204_NO_CONTENT)
async def update_photo_settings(
    photo_id: str, 
    settings: EditorSettingsRequest,
    current_user: UserData = Depends(get_current_user)
):
    """Update editor settings for a specific photo."""
    try:
        products_ref = db.collection('products').where('userId', '==', current_user.uid).stream()
        
        for product_doc in products_ref:
            photo_ref = product_doc.reference.collection('photos').document(photo_id)
            photo_doc_result = photo_ref.get()
            
            if photo_doc_result.exists:
                update_data = settings.model_dump(exclude_unset=True)
                photo_ref.update({
                    "editorSettings": update_data, 
                    "updatedAt": datetime.now()
                })
                
                logger.info(f"Fotoğraf ayarları güncellendi: {photo_id}")
                return
        
        logger.warning(f"Fotoğraf bulunamadı (settings update): {photo_id}")
        raise HTTPException(status_code=404, detail="Fotoğraf bulunamadı veya yetkiniz yok.")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fotoğraf ayarları güncelleme hatası: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Fotoğraf ayarları güncellenirken bir hata oluştu.")

@router.delete("/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_photo(
    photo_id: str,
    current_user: UserData = Depends(get_current_user)
):
    """Delete a specific photo."""
    try:
        products_ref = db.collection('products').where('userId', '==', current_user.uid).stream()
        
        for product_doc in products_ref:
            photo_ref = product_doc.reference.collection('photos').document(photo_id)
            photo_doc_result = photo_ref.get()
            
            if photo_doc_result.exists:
                # TODO: Delete files from storage
                photo_ref.delete()
                logger.info(f"Fotoğraf silindi: {photo_id}")
                return
        
        logger.warning(f"Fotoğraf bulunamadı (delete): {photo_id}")
        raise HTTPException(status_code=404, detail="Fotoğraf bulunamadı veya yetkiniz yok.")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fotoğraf silme hatası: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Fotoğraf silinirken bir hata oluştu.")
