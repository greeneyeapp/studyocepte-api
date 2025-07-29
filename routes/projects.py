# studyocepte-api/routes/projects.py
import io
from datetime import datetime, timedelta
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, status, Depends
from typing import List
from concurrent.futures import ThreadPoolExecutor
import os
import uuid
from loguru import logger
from firebase_admin import firestore

from core.firebase_config import db
from core.storage_config import storage_client
from core.models import UserData, ProjectDetailResponse, ProjectListResponse, EditorSettingsRequest
from core.dependencies import get_current_user
from core.config import settings
from rembg import remove, new_session

router = APIRouter()
REMBG_SESSION = new_session("isnet-general-use")
executor = ThreadPoolExecutor(max_workers=os.cpu_count() or 4)

def apply_mask_to_image(original_bytes: bytes, mask_image: "Image.Image") -> bytes:
    from PIL import Image
    input_image = Image.open(io.BytesIO(original_bytes))
    if input_image.mode != 'RGBA':
        input_image = input_image.convert('RGBA')
    
    alpha = mask_image.convert("L")
    input_image.putalpha(alpha)
    
    output_buffer = io.BytesIO()
    input_image.save(output_buffer, format="PNG")
    return output_buffer.getvalue()

def process_image_in_background(original_image_bytes: bytes, user_id: str, project_id: str):
    logger.info(f"Arka plan işleme başlatıldı: Proje ID: {project_id}")
    try:
        output_image_bytes = remove(original_image_bytes, session=REMBG_SESSION)
        logger.info(f"Proje {project_id} için arka plan silindi.")

        bucket = storage_client.bucket(settings.STORAGE_BUCKET_NAME)
        processed_file_name = f"projects/{user_id}/processed/{uuid.uuid4()}.png"
        processed_blob = bucket.blob(processed_file_name)
        
        processed_blob.upload_from_string(output_image_bytes, content_type="image/png")
        processed_gcs_path = f"gs://{settings.STORAGE_BUCKET_NAME}/{processed_file_name}"
        
        project_ref = db.collection('projects').document(project_id)
        project_ref.update({
            "processedImageUrl": processed_gcs_path,
            "thumbnailUrl": processed_gcs_path,
            "updatedAt": datetime.now(),
            "status": "completed"
        })
        logger.info(f"Firestore'da proje {project_id} güncellendi. Durum: completed")
    except Exception as e:
        logger.error(f"Arka plan işleme thread'inde hata: {e}", exc_info=True)
        project_ref = db.collection('projects').document(project_id)
        project_ref.update({"status": "failed", "errorMessage": str(e), "updatedAt": datetime.now()})

@router.get("/", response_model=List[ProjectListResponse])
async def get_user_projects(current_user: UserData = Depends(get_current_user)):
    try:
        projects_ref = db.collection('projects').where('userId', '==', current_user.uid).order_by('createdAt', direction=firestore.Query.DESCENDING).stream()
        projects = []
        for doc in projects_ref:
            project_data = doc.to_dict()
            project_data['id'] = doc.id
            
            gcs_path = project_data.get('thumbnailUrl')
            if gcs_path and gcs_path.startswith(f"gs://{settings.STORAGE_BUCKET_NAME}/"):
                try:
                    blob_path = gcs_path.replace(f"gs://{settings.STORAGE_BUCKET_NAME}/", "")
                    bucket = storage_client.bucket(settings.STORAGE_BUCKET_NAME)
                    blob = bucket.blob(blob_path)
                    signed_url = blob.generate_signed_url(version="v4", expiration=timedelta(minutes=15), method="GET")
                    project_data['thumbnailUrl'] = signed_url
                except Exception as url_e:
                    project_data['thumbnailUrl'] = ""
            
            projects.append(ProjectListResponse.model_validate(project_data))
        return projects
    except Exception as e:
        logger.error(f"Projeler çekilirken hata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Projeler yüklenirken bir hata oluştu.")

@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project_by_id(project_id: str, current_user: UserData = Depends(get_current_user)):
    try:
        project_ref = db.collection('projects').document(project_id)
        project_doc = project_ref.get()

        if not project_doc.exists:
            raise HTTPException(status_code=404, detail="Proje bulunamadı")
        
        project_data = project_doc.to_dict()
        if project_data.get('userId') != current_user.uid:
            raise HTTPException(status_code=403, detail="Bu projeyi görüntüleme yetkiniz yok.")
        
        project_data['id'] = project_doc.id
        
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

        project_data['thumbnailUrl'] = get_signed_url(project_data.get('thumbnailUrl'))
        project_data['processedImageUrl'] = get_signed_url(project_data.get('processedImageUrl'))

        return ProjectDetailResponse.model_validate(project_data)
    except Exception as e:
        logger.error(f"Proje detayı çekilirken hata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Proje detayı alınırken bir hata oluştu.")

@router.post("/upload-image", response_model=ProjectListResponse)
async def create_project_with_image(
    file: UploadFile = File(...), 
    name: str = Form(...),
    current_user: UserData = Depends(get_current_user)
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Yüklenen dosya bir resim değil.")

    original_image_bytes = await file.read()
    
    try:
        now = datetime.now()
        new_project_ref = db.collection('projects').document()
        new_project_id = new_project_ref.id

        raw_file_name = f"projects/{current_user.uid}/raw/{uuid.uuid4()}_{file.filename}"
        
        new_project_data = {
            "name": name, "userId": current_user.uid,
            "rawImageUrl": f"gs://{settings.STORAGE_BUCKET_NAME}/{raw_file_name}",
            "processedImageUrl": "", "thumbnailUrl": "",
            "createdAt": now, "updatedAt": now,
            "editorSettings": {}, "status": "processing"
        }
        new_project_ref.set(new_project_data)
        
        bucket = storage_client.bucket(settings.STORAGE_BUCKET_NAME)
        raw_blob = bucket.blob(raw_file_name)
        raw_blob.upload_from_string(original_image_bytes, content_type=file.content_type)

        executor.submit(
            process_image_in_background,
            original_image_bytes,
            current_user.uid,
            new_project_id
        )
        
        response_data = {**new_project_data, "id": new_project_id}
        return ProjectListResponse.model_validate(response_data)
    except Exception as e:
        logger.error(f"Resim yükleme sırasında hata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Resim yüklenirken bir hata oluştu: {str(e)}")

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: str, current_user: UserData = Depends(get_current_user)):
    project_ref = db.collection('projects').document(project_id)
    project_doc = project_ref.get()
    if not project_doc.exists or project_doc.to_dict().get('userId') != current_user.uid:
        raise HTTPException(status_code=404, detail="Proje bulunamadı veya silme yetkiniz yok.")
    
    # Storage'dan dosyaları sil (opsiyonel ama önerilir)
    # ...

    project_ref.delete()
    return

@router.put("/{project_id}/settings")
async def update_project_settings(project_id: str, settings_request: EditorSettingsRequest, current_user: UserData = Depends(get_current_user)):
    project_ref = db.collection('projects').document(project_id)
    if not project_ref.get().exists or project_ref.get().to_dict().get('userId') != current_user.uid:
         raise HTTPException(status_code=404, detail="Proje bulunamadı veya güncelleme yetkiniz yok.")
    
    update_data = settings_request.model_dump(exclude_unset=True)
    project_ref.update({"editorSettings": update_data, "updatedAt": datetime.now()})
    return {"message": "Proje ayarları başarıyla güncellendi"}