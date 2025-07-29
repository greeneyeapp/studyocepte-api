import io
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, status, Depends
from typing import List
from concurrent.futures import ThreadPoolExecutor
import os
from loguru import logger
from firebase_admin import firestore

from core.firebase_config import db
from core.storage_config import storage_client
# DÜZELTME: ProductBase buraya eklendi. Hata buydu.
from core.models import UserData, ProductListResponse, ProductDetailResponse, ProductPhotoBase, ProductBase, CreateProductRequest, EditorSettings
from core.dependencies import get_current_user
from core.config import settings
from rembg import remove, new_session

router = APIRouter()
REMBG_SESSION = new_session("isnet-general-use")
executor = ThreadPoolExecutor(max_workers=os.cpu_count() or 4)

def process_image_in_background(original_image_bytes: bytes, user_id: str, product_id: str, photo_id: str):
    logger.info(f"Arka plan işleme başlatıldı: Ürün ID: {product_id}, Foto ID: {photo_id}")
    try:
        output_image_bytes = remove(original_image_bytes, session=REMBG_SESSION)
        
        bucket = storage_client.bucket(settings.STORAGE_BUCKET_NAME)
        processed_file_name = f"products/{user_id}/photos/{photo_id}_processed.png"
        processed_blob = bucket.blob(processed_file_name)
        processed_blob.upload_from_string(output_image_bytes, content_type="image/png")
        
        photo_ref = db.collection('products').document(product_id).collection('photos').document(photo_id)
        photo_ref.update({
            "processedImageUrl": f"gs://{settings.STORAGE_BUCKET_NAME}/{processed_file_name}",
            "thumbnailUrl": f"gs://{settings.STORAGE_BUCKET_NAME}/{processed_file_name}",
            "updatedAt": datetime.now(),
            "status": "completed"
        })
        logger.info(f"Firestore'da fotoğraf {photo_id} güncellendi. Durum: completed")
    except Exception as e:
        logger.error(f"Arka plan işleme thread'inde hata: {e}", exc_info=True)
        photo_ref = db.collection('products').document(product_id).collection('photos').document(photo_id)
        photo_ref.update({"status": "failed", "errorMessage": str(e), "updatedAt": datetime.now()})

def get_signed_url(gcs_path):
    if not gcs_path or not gcs_path.startswith(f"gs://{settings.STORAGE_BUCKET_NAME}/"): return ""
    try:
        blob_path = gcs_path.replace(f"gs://{settings.STORAGE_BUCKET_NAME}/", "")
        bucket = storage_client.bucket(settings.STORAGE_BUCKET_NAME)
        blob = bucket.blob(blob_path)
        return blob.generate_signed_url(version="v4", expiration=timedelta(minutes=15), method="GET")
    except Exception as e:
        logger.warning(f"İmzalı URL hatası ({gcs_path}): {e}")
        return ""

@router.get("/", response_model=List[ProductListResponse])
async def get_user_products(current_user: UserData = Depends(get_current_user)):
    products_ref = db.collection('products').where('userId', '==', current_user.uid).order_by('createdAt', direction=firestore.Query.DESCENDING).stream()
    products_list = []
    for doc in products_ref:
        product_data = doc.to_dict()
        product_data['id'] = doc.id
        
        photos_collection = doc.reference.collection('photos').order_by('createdAt', direction=firestore.Query.DESCENDING).limit(1).stream()
        first_photo = next(photos_collection, None)
        
        photo_count_query = doc.reference.collection('photos').stream()
        photo_count = len(list(photo_count_query))

        product_data['photoCount'] = photo_count

        if first_photo:
            product_data['coverThumbnailUrl'] = get_signed_url(first_photo.to_dict().get('thumbnailUrl'))
        else:
            product_data['coverThumbnailUrl'] = None
            
        products_list.append(ProductListResponse.model_validate(product_data))
    return products_list

@router.post("/", response_model=ProductBase)
async def create_product(request: CreateProductRequest, current_user: UserData = Depends(get_current_user)):
    new_product_ref = db.collection('products').document()
    now = datetime.now()
    product_data = {
        "id": new_product_ref.id,
        "name": request.name,
        "userId": current_user.uid,
        "createdAt": now,
        "updatedAt": now
    }
    new_product_ref.set(product_data)
    # model_validate yerine pydantic v1 için from_orm kullanılabilir
    return ProductBase.model_validate(product_data)

@router.post("/{product_id}/photos", response_model=ProductPhotoBase)
async def upload_photo_to_product(
    product_id: str,
    file: UploadFile = File(...),
    current_user: UserData = Depends(get_current_user)
):
    product_ref = db.collection('products').document(product_id)
    product_doc = product_ref.get()
    if not product_doc.exists or product_doc.to_dict().get('userId') != current_user.uid:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı veya yetkiniz yok.")

    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Yüklenen dosya bir resim değil.")

    original_image_bytes = await file.read()
    now = datetime.now()
    new_photo_ref = product_ref.collection('photos').document()
    new_photo_id = new_photo_ref.id

    raw_file_name = f"products/{current_user.uid}/photos/{new_photo_id}_raw.png"
    
    photo_data = {
        "id": new_photo_id,
        "productId": product_id,
        "userId": current_user.uid,
        "rawImageUrl": f"gs://{settings.STORAGE_BUCKET_NAME}/{raw_file_name}",
        "processedImageUrl": "",
        "thumbnailUrl": "",
        "createdAt": now,
        "updatedAt": now,
        "editorSettings": {},
        "status": "processing"
    }
    new_photo_ref.set(photo_data)

    bucket = storage_client.bucket(settings.STORAGE_BUCKET_NAME)
    raw_blob = bucket.blob(raw_file_name)
    raw_blob.upload_from_string(original_image_bytes, content_type=file.content_type)

    executor.submit(
        process_image_in_background,
        original_image_bytes,
        current_user.uid,
        product_id,
        new_photo_id
    )
    
    return ProductPhotoBase.model_validate(photo_data)


@router.get("/{product_id}", response_model=ProductDetailResponse)
async def get_product_details(product_id: str, current_user: UserData = Depends(get_current_user)):
    product_ref = db.collection('products').document(product_id)
    product_doc = product_ref.get()
    if not product_doc.exists or product_doc.to_dict().get('userId') != current_user.uid:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı.")
        
    product_data = product_doc.to_dict()
    product_data['id'] = product_doc.id
    
    photos_stream = product_ref.collection('photos').order_by('createdAt', direction=firestore.Query.DESCENDING).stream()
    photos_list = []
    for photo_doc in photos_stream:
        photo_data = photo_doc.to_dict()
        photo_data['id'] = photo_doc.id
        photo_data['thumbnailUrl'] = get_signed_url(photo_data.get('thumbnailUrl'))
        photo_data['processedImageUrl'] = get_signed_url(photo_data.get('processedImageUrl'))
        photos_list.append(ProductPhotoBase.model_validate(photo_data))
        
    product_data['photos'] = photos_list
    return ProductDetailResponse.model_validate(product_data)

@router.put("/{product_id}/photos/{photo_id}/settings", status_code=status.HTTP_204_NO_CONTENT)
async def update_photo_settings(
    product_id: str, 
    photo_id: str, 
    settings: EditorSettings,
    current_user: UserData = Depends(get_current_user)
):
    photo_ref = db.collection('products').document(product_id).collection('photos').document(photo_id)
    photo_doc = photo_ref.get()

    if not photo_doc.exists or photo_doc.to_dict().get('userId') != current_user.uid:
        raise HTTPException(status_code=404, detail="Fotoğraf bulunamadı veya yetkiniz yok.")
    
    update_data = settings.model_dump(exclude_unset=True)
    photo_ref.update({"editorSettings": update_data, "updatedAt": datetime.now()})
    return