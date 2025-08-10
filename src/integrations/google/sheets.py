from typing import List, Dict, Any, Optional
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import structlog

import sys
from pathlib import Path

# Add project root to path for proper imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from core.config import settings

logger = structlog.get_logger(__name__)


class GoogleSheetsService:
    """Service for Google Sheets operations"""
    
    def __init__(self):
        self.credentials = self._get_credentials()
        self.gc = gspread.authorize(self.credentials)
        self.manifest_sheet_id = settings.google_sheets_manifest_id
        self._worksheet = None
    
    def _get_credentials(self) -> Credentials:
        """Get Google service account credentials"""
        credentials_info = settings.google_credentials_dict
        credentials = Credentials.from_service_account_info(
            credentials_info,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        return credentials
    
    def _get_worksheet(self):
        """Get or create worksheet"""
        if self._worksheet is None:
            try:
                sheet = self.gc.open_by_key(self.manifest_sheet_id)
                self._worksheet = sheet.get_worksheet(0)  # First worksheet
            except Exception as e:
                logger.error("Failed to open manifest sheet", error=str(e))
                raise
        return self._worksheet
    
    async def ensure_headers(self):
        """Ensure headers exist in the manifest sheet"""
        worksheet = self._get_worksheet()
        
        headers = [
            "creative_id",
            "geo", 
            "drive_file_id",
            "drive_link",
            "uploader_tg_id",
            "uploader_buyer_id",
            "original_name",
            "mime_type",
            "size_bytes",
            "sha256",
            "upload_dt_msk",
            "notes"
        ]
        
        try:
            # Check if headers already exist
            existing_headers = worksheet.row_values(1)
            
            if not existing_headers or existing_headers != headers:
                # Set headers
                worksheet.update("A1", [headers])
                logger.info("Headers updated in manifest sheet")
            
        except Exception as e:
            logger.error("Failed to ensure headers", error=str(e))
            raise
    
    async def add_creative_record(self, creative_data: Dict[str, Any]) -> bool:
        """Add creative record to manifest sheet"""
        try:
            worksheet = self._get_worksheet()
            
            # Ensure headers exist
            await self.ensure_headers()
            
            # Prepare row data
            row_data = [
                creative_data.get("creative_id", ""),
                creative_data.get("geo", ""),
                creative_data.get("drive_file_id", ""),
                creative_data.get("drive_link", ""),
                creative_data.get("uploader_tg_id", ""),
                creative_data.get("uploader_buyer_id", ""),
                creative_data.get("original_name", ""),
                creative_data.get("mime_type", ""),
                creative_data.get("size_bytes", ""),
                creative_data.get("sha256", ""),
                creative_data.get("upload_dt_msk", ""),
                creative_data.get("notes", "")
            ]
            
            # Add row
            worksheet.append_row(row_data)
            
            logger.info(
                "Creative record added to manifest",
                creative_id=creative_data.get("creative_id")
            )
            return True
            
        except Exception as e:
            logger.error(
                "Failed to add creative record",
                creative_id=creative_data.get("creative_id"),
                error=str(e)
            )
            return False
    
    async def update_creative_record(
        self,
        creative_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """Update creative record in manifest sheet"""
        try:
            worksheet = self._get_worksheet()
            
            # Find row with creative_id
            cell = worksheet.find(creative_id)
            if not cell:
                logger.warning(
                    "Creative ID not found in manifest",
                    creative_id=creative_id
                )
                return False
            
            row_num = cell.row
            
            # Get headers to map column positions
            headers = worksheet.row_values(1)
            
            # Update specific columns
            for field, value in updates.items():
                if field in headers:
                    col_num = headers.index(field) + 1
                    worksheet.update_cell(row_num, col_num, value)
            
            logger.info(
                "Creative record updated in manifest",
                creative_id=creative_id,
                updates=list(updates.keys())
            )
            return True
            
        except Exception as e:
            logger.error(
                "Failed to update creative record",
                creative_id=creative_id,
                error=str(e)
            )
            return False
    
    async def get_creative_record(self, creative_id: str) -> Optional[Dict[str, Any]]:
        """Get creative record from manifest sheet"""
        try:
            worksheet = self._get_worksheet()
            
            # Find row with creative_id
            cell = worksheet.find(creative_id)
            if not cell:
                return None
            
            row_num = cell.row
            headers = worksheet.row_values(1)
            row_data = worksheet.row_values(row_num)
            
            # Create record dict
            record = {}
            for i, header in enumerate(headers):
                record[header] = row_data[i] if i < len(row_data) else ""
            
            return record
            
        except Exception as e:
            logger.error(
                "Failed to get creative record",
                creative_id=creative_id,
                error=str(e)
            )
            return None
    
    async def get_all_records(self) -> List[Dict[str, Any]]:
        """Get all records from manifest sheet"""
        try:
            worksheet = self._get_worksheet()
            records = worksheet.get_all_records()
            return records
            
        except Exception as e:
            logger.error("Failed to get all records", error=str(e))
            return []