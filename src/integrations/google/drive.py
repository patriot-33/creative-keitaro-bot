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
        logger.info(f"Ensuring GEO folder exists for: {geo}")
        logger.info(f"Root folder ID: {self.root_folder_id}")
        
        try:
            # Search for existing folder
            query = (
                f"name='{geo}' and "
                f"parents in '{self.root_folder_id}' and "
                "mimeType='application/vnd.google-apps.folder' and "
                "trashed=false"
            )
            logger.info(f"Search query: {query}")
            
            logger.info("Searching for existing GEO folder...")
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name, parents)'
            ).execute()
            logger.info(f"Search results: {results}")
            
            folders = results.get('files', [])
            logger.info(f"Found {len(folders)} matching folders")
            
            if folders:
                folder_id = folders[0]['id']
                folder_name = folders[0]['name']
                folder_parents = folders[0].get('parents', [])
                logger.info(f"Using existing GEO folder: {folder_name} (ID: {folder_id})")
                logger.info(f"Folder parents: {folder_parents}")
                return folder_id
            
            # Create new folder
            logger.info("No existing folder found, creating new GEO folder...")
            folder_metadata = {
                'name': geo,
                'parents': [self.root_folder_id],
                'mimeType': 'application/vnd.google-apps.folder'
            }
            logger.info(f"Folder metadata: {folder_metadata}")
            
            logger.info("Creating folder via Google Drive API...")
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id,name,parents'
            ).execute()
            logger.info(f"Folder creation response: {folder}")
            
            folder_id = folder.get('id')
            folder_name = folder.get('name')
            folder_parents = folder.get('parents', [])
            
            logger.info(f"Created new GEO folder successfully!")
            logger.info(f"  - Name: {folder_name}")
            logger.info(f"  - ID: {folder_id}")  
            logger.info(f"  - Parents: {folder_parents}")
            logger.info(f"  - GEO: {geo}")
            
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
        logger.info(f"Starting file upload: {filename} ({len(file_content)} bytes) to GEO: {geo}")
        logger.info(f"MIME type: {mime_type}")
        logger.info(f"Root folder ID: {self.root_folder_id}")
        
        try:
            # Ensure GEO folder exists
            logger.info(f"Ensuring GEO folder exists for: {geo}")
            folder_id = await self.ensure_geo_folder(geo)
            logger.info(f"GEO folder ID: {folder_id}")
            
            # Calculate SHA256 hash
            logger.info("Calculating SHA256 hash...")
            sha256_hash = hashlib.sha256(file_content).hexdigest()
            logger.info(f"SHA256 hash: {sha256_hash[:16]}...")
            
            # Create file stream
            logger.info("Creating file stream...")
            file_stream = io.BytesIO(file_content)
            file_stream.seek(0)  # Reset stream position
            logger.info(f"File stream created, size: {len(file_content)} bytes")
            
            # File metadata
            file_metadata = {
                'name': filename,
                'parents': [folder_id]
            }
            logger.info(f"File metadata: {file_metadata}")
            
            # Upload file
            logger.info("Creating MediaIoBaseUpload...")
            media = MediaIoBaseUpload(
                file_stream,
                mimetype=mime_type,
                resumable=True
            )
            logger.info("MediaIoBaseUpload created successfully")
            
            logger.info("Starting Google Drive API upload...")
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,webViewLink,name,size,mimeType'
            ).execute()
            logger.info(f"Google Drive API response: {file}")
            
            file_id = file.get('id')
            web_view_link = file.get('webViewLink')
            uploaded_name = file.get('name')
            uploaded_size = file.get('size')
            uploaded_mime = file.get('mimeType')
            
            logger.info(f"File uploaded successfully!")
            logger.info(f"  - File ID: {file_id}")
            logger.info(f"  - Name: {uploaded_name}")
            logger.info(f"  - Size: {uploaded_size} bytes")
            logger.info(f"  - MIME: {uploaded_mime}")
            logger.info(f"  - URL: {web_view_link}")
            logger.info(f"  - GEO folder: {geo} ({folder_id})")
            
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