"""
Telegram-based file storage service
"""

import logging
import hashlib
from typing import Tuple, Optional
from aiogram import Bot
from aiogram.types import Message, InputMediaPhoto, InputMediaVideo, InputMediaDocument

import sys
from pathlib import Path

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from core.config import settings

logger = logging.getLogger(__name__)


class TelegramStorageService:
    """Service for storing files in Telegram"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        # You can create a dedicated storage chat/channel for files
        # For now, we'll use the file_id from the original message
    
    async def store_creative(
        self, 
        file_id: str,
        file_name: str,
        file_size: int,
        mime_type: str,
        creative_id: str,
        geo: str
    ) -> Tuple[str, Optional[int], str]:
        """
        Store creative file in Telegram
        
        Returns:
            Tuple of (telegram_file_id, message_id, sha256_hash)
        """
        logger.info(f"Storing creative in Telegram: {creative_id}")
        logger.info(f"File details: name={file_name}, size={file_size}, mime={mime_type}")
        
        try:
            # Calculate hash from file content
            file_info = await self.bot.get_file(file_id)
            file_bytes = await self.bot.download_file(file_info.file_path)
            sha256_hash = hashlib.sha256(file_bytes.read()).hexdigest()
            
            # For now, we'll just store the original file_id
            # In a more advanced setup, you could forward the file to a dedicated storage chat
            logger.info(f"Creative stored in Telegram successfully!")
            logger.info(f"  - Creative ID: {creative_id}")
            logger.info(f"  - Telegram File ID: {file_id}")
            logger.info(f"  - File Name: {file_name}")
            logger.info(f"  - Size: {file_size} bytes")
            logger.info(f"  - SHA256: {sha256_hash[:16]}...")
            logger.info(f"  - GEO: {geo}")
            
            return file_id, None, sha256_hash
            
        except Exception as e:
            logger.error(f"Failed to store creative in Telegram: {e}")
            raise
    
    async def get_file_info(self, telegram_file_id: str) -> dict:
        """Get file information from Telegram"""
        try:
            file_info = await self.bot.get_file(telegram_file_id)
            
            return {
                'file_id': telegram_file_id,
                'file_unique_id': file_info.file_unique_id,
                'file_size': file_info.file_size,
                'file_path': file_info.file_path
            }
        except Exception as e:
            logger.error(f"Failed to get Telegram file info: {e}")
            return {}
    
    def create_telegram_link(self, telegram_file_id: str, file_name: str) -> str:
        """Create a link for Telegram file (for display purposes)"""
        # This is not a real URL, but a display string
        return f"telegram://file/{telegram_file_id[:16]}.../{file_name}"
    
    async def send_file_to_chat(self, chat_id: int, telegram_file_id: str, caption: str = "") -> Optional[Message]:
        """Send stored file to a chat"""
        try:
            # Try to send as document to preserve original format
            message = await self.bot.send_document(
                chat_id=chat_id,
                document=telegram_file_id,
                caption=caption
            )
            return message
        except Exception as e:
            logger.error(f"Failed to send file to chat {chat_id}: {e}")
            return None