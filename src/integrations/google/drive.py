import io
import hashlib
from typing import Optional, Tuple
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
import structlog

import sys
from pathlib import Path

# Add project root to path for proper imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from core.config import settings

logger = structlog.get_logger(__name__)


class GoogleDriveService:
    """Service for Google Drive operations"""
    
    def __init__(self):
        self.credentials = self._get_credentials()
        self.service = build("drive", "v3", credentials=self.credentials)
        self.root_folder_id = settings.google_drive_root_folder_id
    
    def _get_credentials(self) -> Credentials:
        """Get Google service account credentials"""
        credentials_info = settings.google_credentials_dict
        credentials = Credentials.from_service_account_info(
            credentials_info,
            scopes=["https://www.googleapis.com/auth/drive"]
        )
        return credentials
    
    async def ensure_geo_folder(self, geo: str) -> str:
        """Ensure GEO folder exists and return its ID"""
        try:
            # Search for existing folder
            query = (
                f"name='{geo}' and "
                f"parents in '{self.root_folder_id}' and "
                "mimeType='application/vnd.google-apps.folder' and "
                "trashed=false"
            )
            
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            folders = results.get('files', [])
            
            if folders:
                folder_id = folders[0]['id']
                logger.info("Found existing GEO folder", geo=geo, folder_id=folder_id)
                return folder_id
            
            # Create new folder
            folder_metadata = {
                'name': geo,
                'parents': [self.root_folder_id],
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            folder_id = folder.get('id')
            logger.info("Created new GEO folder", geo=geo, folder_id=folder_id)
            return folder_id
            
        except Exception as e:
            logger.error("Failed to ensure GEO folder", geo=geo, error=str(e))
            raise
    
    async def upload_file(
        self,
        file_content: bytes,
        filename: str,
        geo: str,
        mime_type: str
    ) -> Tuple[str, str, str]:
        """
        Upload file to Google Drive
        
        Returns:
            Tuple of (file_id, web_view_link, sha256_hash)
        """
        try:
            # Ensure GEO folder exists
            folder_id = await self.ensure_geo_folder(geo)
            
            # Calculate SHA256 hash
            sha256_hash = hashlib.sha256(file_content).hexdigest()
            
            # Create file stream
            file_stream = io.BytesIO(file_content)
            
            # File metadata
            file_metadata = {
                'name': filename,
                'parents': [folder_id]
            }
            
            # Upload file
            media = MediaIoBaseUpload(
                file_stream,
                mimetype=mime_type,
                resumable=True
            )
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,webViewLink'
            ).execute()
            
            file_id = file.get('id')
            web_view_link = file.get('webViewLink')
            
            logger.info(
                "File uploaded successfully",
                filename=filename,
                file_id=file_id,
                geo=geo
            )
            
            return file_id, web_view_link, sha256_hash
            
        except Exception as e:
            logger.error(
                "Failed to upload file",
                filename=filename,
                geo=geo,
                error=str(e)
            )
            raise
    
    async def delete_file(self, file_id: str) -> bool:
        """Delete file from Google Drive"""
        try:
            self.service.files().delete(fileId=file_id).execute()
            logger.info("File deleted successfully", file_id=file_id)
            return True
        except Exception as e:
            logger.error("Failed to delete file", file_id=file_id, error=str(e))
            return False
    
    async def get_file_info(self, file_id: str) -> Optional[dict]:
        """Get file information"""
        try:
            file_info = self.service.files().get(
                fileId=file_id,
                fields='id,name,size,mimeType,webViewLink,createdTime'
            ).execute()
            return file_info
        except Exception as e:
            logger.error("Failed to get file info", file_id=file_id, error=str(e))
            return None