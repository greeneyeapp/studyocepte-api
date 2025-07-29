# studyocepte-api/core/storage_config.py
from google.cloud import storage
import os
from core.firebase_config import google_cloud_credentials # Yeni import: google_cloud_credentials

# storage_client'ı başlatırken google_cloud_credentials parametresini kullanıyoruz
storage_client = storage.Client(credentials=google_cloud_credentials)