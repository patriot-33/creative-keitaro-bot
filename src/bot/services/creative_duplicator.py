"""
Сервис для дублирования креативов в канал хранения
"""

import logging
from typing import Optional
from datetime import datetime
from aiogram import Bot
from aiogram.types import Message

from core.config import settings

logger = logging.getLogger(__name__)


class CreativeDuplicatorService:
    """Сервис для дублирования креативов в канал хранения"""
    
    @staticmethod
    async def duplicate_creative(
        bot: Bot,
        creative_id: str,
        file_id: str,
        file_type: str,  # "photo", "video", "animation", "document"
        geo: str,
        uploader_name: str,
        uploader_username: Optional[str],
        uploader_id: int,
        buyer_id: Optional[str],
        notes: Optional[str],
        custom_name: Optional[str],
        file_name: str,
        file_size: int
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Дублирует креатив в канал хранения
        
        Args:
            bot: Экземпляр бота aiogram
            creative_id: ID креатива (например: IDUS131225001)
            file_id: Telegram file_id
            file_type: Тип файла (photo/video/animation/document)
            geo: Географический регион
            uploader_name: Имя загрузившего пользователя
            uploader_username: Username загрузившего (может быть None)
            uploader_id: Telegram ID загрузившего
            buyer_id: Buyer ID пользователя (может быть None)
            notes: Описание креатива (может быть None)
            custom_name: Пользовательское название (может быть None)
            file_name: Оригинальное имя файла
            file_size: Размер файла в байтах
            
        Returns:
            tuple: (success: bool, message_id: Optional[str], error: Optional[str])
        """
        
        # Проверяем, настроен ли канал для хранения
        if not settings.creative_storage_channel_id:
            logger.info("Канал для хранения креативов не настроен")
            return (True, None, None)  # Не считаем это ошибкой
        
        try:
            # Формируем красивое описание
            caption_parts = [
                f"🎨 <b>Новый креатив загружен!</b>",
                "",
                f"🆔 <b>ID креатива:</b> <code>{creative_id}</code>",
                f"🌍 <b>ГЕО:</b> {geo}",
            ]
            
            # Добавляем информацию о названии
            if custom_name:
                caption_parts.append(f"📝 <b>Название:</b> {custom_name}")
            
            # Информация о пользователе
            user_info = f"👤 <b>Загрузил:</b> {uploader_name}"
            if uploader_username:
                user_info += f" (@{uploader_username})"
            user_info += f" (ID: {uploader_id})"
            caption_parts.append(user_info)
            
            # Buyer ID если есть
            if buyer_id:
                caption_parts.append(f"🏷 <b>Buyer ID:</b> {buyer_id}")
            
            # Информация о файле
            caption_parts.extend([
                f"📄 <b>Файл:</b> {file_name}",
                f"📏 <b>Размер:</b> {file_size / 1024:.0f} КБ",
                f"📅 <b>Дата загрузки:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')} MSK"
            ])
            
            # Описание если есть
            if notes:
                caption_parts.extend([
                    "",
                    f"💬 <b>Описание:</b> {notes}"
                ])
            
            # Хештеги
            caption_parts.extend([
                "",
                f"#креатив #{geo} #загружен"
            ])
            if buyer_id:
                caption_parts.append(f"#{buyer_id}")
            
            caption = "\n".join(caption_parts)
            
            # Ограничение Telegram на caption - 1024 символа
            if len(caption) > 1020:
                caption = caption[:1017] + "..."
            
            # Отправляем сообщение в канал в зависимости от типа файла
            message: Optional[Message] = None
            
            if file_type == "photo":
                message = await bot.send_photo(
                    chat_id=settings.creative_storage_channel_id,
                    photo=file_id,
                    caption=caption,
                    parse_mode="HTML"
                )
            elif file_type == "video":
                message = await bot.send_video(
                    chat_id=settings.creative_storage_channel_id,
                    video=file_id,
                    caption=caption,
                    parse_mode="HTML"
                )
            elif file_type == "animation":
                message = await bot.send_animation(
                    chat_id=settings.creative_storage_channel_id,
                    animation=file_id,
                    caption=caption,
                    parse_mode="HTML"
                )
            else:  # document
                message = await bot.send_document(
                    chat_id=settings.creative_storage_channel_id,
                    document=file_id,
                    caption=caption,
                    parse_mode="HTML"
                )
            
            if message:
                logger.info(f"✅ Креатив {creative_id} успешно отправлен в канал хранения (message_id: {message.message_id})")
                return (True, str(message.message_id), None)
            else:
                logger.error(f"❌ Не удалось отправить креатив {creative_id} в канал")
                return (False, None, "Message not sent")
                        
        except Exception as e:
            logger.error(f"❌ Исключение при дублировании креатива {creative_id}: {e}")
            return (False, None, str(e))
    
    @staticmethod
    async def duplicate_with_retry(
        bot: Bot,
        creative_id: str,
        file_id: str,
        file_type: str,
        geo: str,
        uploader_name: str,
        uploader_username: Optional[str],
        uploader_id: int,
        buyer_id: Optional[str],
        notes: Optional[str],
        custom_name: Optional[str],
        file_name: str,
        file_size: int,
        max_retries: int = 3
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Дублирует креатив с повторными попытками при неудаче
        
        Args:
            bot: Экземпляр бота aiogram
            max_retries: Максимальное количество попыток
            (остальные аргументы как в duplicate_creative)
            
        Returns:
            tuple: (success: bool, message_id: Optional[str], error: Optional[str])
        """
        
        last_error = None
        for attempt in range(max_retries):
            success, message_id, error = await CreativeDuplicatorService.duplicate_creative(
                bot=bot,
                creative_id=creative_id,
                file_id=file_id,
                file_type=file_type,
                geo=geo,
                uploader_name=uploader_name,
                uploader_username=uploader_username,
                uploader_id=uploader_id,
                buyer_id=buyer_id,
                notes=notes,
                custom_name=custom_name,
                file_name=file_name,
                file_size=file_size
            )
            
            if success:
                return (True, message_id, None)
            
            last_error = error
            
            if attempt < max_retries - 1:
                logger.info(f"Повторная попытка {attempt + 2}/{max_retries} дублирования креатива {creative_id}")
                # Небольшая задержка перед повторной попыткой
                import asyncio
                await asyncio.sleep(1)
        
        logger.error(f"❌ Не удалось продублировать креатив {creative_id} после {max_retries} попыток. Последняя ошибка: {last_error}")
        return (False, None, last_error)