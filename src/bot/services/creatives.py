"""
Сервис для работы с креативами
"""

import logging
from typing import List, Optional
from datetime import datetime

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db_session
from db.models.creative import Creative

logger = logging.getLogger(__name__)


class CreativesService:
    """Сервис для работы с креативами"""
    
    @staticmethod
    async def get_user_creatives(
        user_id: int, 
        limit: int = 10, 
        offset: int = 0
    ) -> List[Creative]:
        """Получить креативы пользователя"""
        try:
            async with get_db_session() as session:
                stmt = (
                    select(Creative)
                    .where(Creative.uploader_user_id == user_id)
                    .order_by(desc(Creative.upload_dt))
                    .limit(limit)
                    .offset(offset)
                )
                result = await session.execute(stmt)
                return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting user creatives: {e}")
            return []
    
    @staticmethod
    async def get_creative_by_id(creative_id: str) -> Optional[Creative]:
        """Получить креатив по ID"""
        try:
            async with get_db_session() as session:
                stmt = select(Creative).where(Creative.creative_id == creative_id)
                result = await session.execute(stmt)
                return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting creative by ID {creative_id}: {e}")
            return None
    
    @staticmethod
    async def count_user_creatives(user_id: int) -> int:
        """Подсчитать количество креативов пользователя"""
        try:
            async with get_db_session() as session:
                from sqlalchemy import func
                stmt = (
                    select(func.count(Creative.creative_id))
                    .where(Creative.uploader_user_id == user_id)
                )
                result = await session.execute(stmt)
                return result.scalar() or 0
        except Exception as e:
            logger.error(f"Error counting user creatives: {e}")
            return 0
    
    @staticmethod
    def format_creative_info(creative: Creative) -> str:
        """Форматировать информацию о креативе"""
        size_mb = round(creative.size_bytes / (1024 * 1024), 1) if creative.size_bytes else 0
        upload_date = creative.upload_dt.strftime("%d.%m.%Y %H:%M") if creative.upload_dt else "Неизвестно"
        
        return f"""🎨 <b>{creative.creative_id}</b>
🌍 GEO: {creative.geo}
📝 Имя: {creative.original_name or 'Не указано'}
📊 Размер: {size_mb} MB
📅 Загружен: {upload_date}
🔗 <a href="{creative.drive_link}">Открыть в Google Drive</a>
"""