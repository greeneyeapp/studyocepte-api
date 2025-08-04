import io
import asyncio
from typing import List
import numpy as np
from fastapi import APIRouter, File, UploadFile, HTTPException, status
from fastapi.responses import JSONResponse
from rembg import remove, new_session
from PIL import Image
from skimage import morphology
from scipy.ndimage import gaussian_filter
from loguru import logger
import base64

router = APIRouter()
REMBG_SESSION = new_session("isnet-general-use")

def apply_mask_to_image(original_bytes: bytes, mask_image: Image.Image) -> bytes:
    """Görüntüye maskeyi uygular ve PNG olarak döndürür."""
    input_image = Image.open(io.BytesIO(original_bytes))
    if input_image.mode != 'RGBA':
        input_image = input_image.convert('RGBA')
    
    alpha = mask_image.convert("L")
    input_image.putalpha(alpha)
    
    output_buffer = io.BytesIO()
    input_image.save(output_buffer, format="PNG")
    return output_buffer.getvalue()

async def process_single_image(file: UploadFile) -> bytes:
    """Tek bir resmi işleyen ve byte dizisini döndüren asenkron fonksiyon."""
    logger.info(f"İşleniyor: {file.filename}")
    input_image_bytes = await file.read()
    
    body_mask_bytes = remove(input_image_bytes, session=REMBG_SESSION, only_mask=True, alpha_matting=False)
    body_mask = Image.open(io.BytesIO(body_mask_bytes)).convert("L")

    details_mask_bytes = remove(
        input_image_bytes, session=REMBG_SESSION, only_mask=True,
        alpha_matting=True, alpha_matting_foreground_threshold=200,
        alpha_matting_background_threshold=20, alpha_matting_erode_size=10
    )
    details_mask = Image.open(io.BytesIO(details_mask_bytes)).convert("L")
    
    body_array = np.array(body_mask) > 127
    details_array = np.array(details_mask) > 127
    combined_array = np.logical_or(body_array, details_array)
    
    cleaned_array = morphology.remove_small_objects(combined_array, min_size=250)
    filled_array = morphology.remove_small_holes(cleaned_array, area_threshold=150)
    smoothed_array = gaussian_filter(filled_array.astype(float), sigma=1)
    final_mask = Image.fromarray((smoothed_array * 255).astype(np.uint8))
    
    return apply_mask_to_image(input_image_bytes, final_mask)

@router.post("/remove-background/batch/")
async def remove_background_batch(files: List[UploadFile] = File(...)):
    """Birden fazla fotoğrafın arka planını temizler ve base64 olarak döndürür."""
    if not files:
        raise HTTPException(status_code=400, detail="İşlenecek dosya bulunamadı.")
        
    logger.info(f"Toplu arka plan kaldırma isteği alındı: {len(files)} dosya")
    
    results = {"success": {}, "errors": {}}

    async def process_and_store(file: UploadFile):
        try:
            processed_bytes = await process_single_image(file)
            encoded_string = base64.b64encode(processed_bytes).decode('utf-8')
            results["success"][file.filename] = encoded_string
        except Exception as e:
            logger.error(f"Dosya işlenirken hata oluştu: {file.filename}, Hata: {e}")
            results["errors"][file.filename] = str(e)

    await asyncio.gather(*(process_and_store(file) for file in files))

    logger.info(f"Toplu işlem tamamlandı. Başarılı: {len(results['success'])}, Hatalı: {len(results['errors'])}")
    return JSONResponse(content=results)