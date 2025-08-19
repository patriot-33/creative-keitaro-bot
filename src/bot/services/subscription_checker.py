"""
Сервис проверки подписки на обязательный канал
"""

import logging
from typing import Optional
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import ChatMemberOwner, ChatMemberAdministrator, ChatMemberMember

from core.config import settings

logger = logging.getLogger(__name__)


class SubscriptionChecker:
    """Сервис для проверки подписки пользователя на обязательный канал"""
    
    @staticmethod
    async def is_user_subscribed(bot: Bot, user_id: int) -> bool:
        """
        Проверяет, подписан ли пользователь на обязательный канал
        
        Args:
            bot: Экземпляр бота
            user_id: ID пользователя Telegram
            
        Returns:
            bool: True если подписан, False если не подписан
        """
        
        # Проверяем, настроен ли обязательный канал
        if not settings.required_channel_id:
            logger.info("Обязательный канал не настроен, проверка подписки пропущена")
            return True
        
        try:
            # Получаем информацию о членстве пользователя в канале
            member = await bot.get_chat_member(
                chat_id=settings.required_channel_id,
                user_id=user_id
            )
            
            # Проверяем статус подписки
            if isinstance(member, (ChatMemberOwner, ChatMemberAdministrator, ChatMemberMember)):
                logger.info(f"✅ Пользователь {user_id} подписан на канал {settings.required_channel_id}")
                return True
            else:
                logger.info(f"❌ Пользователь {user_id} не подписан на канал {settings.required_channel_id}, статус: {member.status}")
                return False
                
        except TelegramBadRequest as e:
            # Пользователь не найден в канале или канал не существует
            logger.warning(f"❌ Ошибка проверки подписки для пользователя {user_id}: {e}")
            return False
            
        except TelegramForbiddenError as e:
            # Бот не имеет прав для проверки участников канала
            logger.error(f"❌ Бот не имеет прав для проверки подписки на канал {settings.required_channel_id}: {e}")
            return True  # Пропускаем проверку если нет прав
            
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при проверке подписки пользователя {user_id}: {e}")
            return True  # В случае ошибки разрешаем доступ

    @staticmethod
    async def get_channel_info(bot: Bot) -> Optional[dict]:
        """
        Получает информацию о канале для отображения пользователю
        
        Args:
            bot: Экземпляр бота
            
        Returns:
            dict: Информация о канале или None если канал недоступен
        """
        
        if not settings.required_channel_id:
            return None
            
        try:
            chat = await bot.get_chat(settings.required_channel_id)
            
            # Получаем invite_link если его нет в chat объекте
            invite_link = chat.invite_link
            if not invite_link:
                try:
                    # Пытаемся экспортировать invite link
                    invite_link = await bot.export_chat_invite_link(settings.required_channel_id)
                    logger.info(f"🔗 Generated invite link for channel {settings.required_channel_id}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not generate invite link for channel {settings.required_channel_id}: {e}")
                    invite_link = None
            
            return {
                'id': chat.id,
                'title': chat.title or 'Канал',
                'username': chat.username,
                'invite_link': invite_link
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения информации о канале {settings.required_channel_id}: {e}")
            return None

    @staticmethod
    async def get_channel_link(bot: Bot) -> Optional[str]:
        """
        Возвращает ссылку на канал для подписки
        
        Args:
            bot: Экземпляр бота для получения актуальной ссылки
            
        Returns:
            str: Ссылка на канал или None если не настроено
        """
        
        if not settings.required_channel_id:
            return None
        
        # Сначала проверяем есть ли заданная вручную ссылка
        if hasattr(settings, 'required_channel_invite_link') and settings.required_channel_invite_link:
            logger.info(f"🔗 Using configured invite link for channel {settings.required_channel_id}")
            return settings.required_channel_invite_link
        
        # Получаем актуальную информацию о канале включая invite_link
        channel_info = await SubscriptionChecker.get_channel_info(bot)
        
        if channel_info and channel_info.get('invite_link'):
            return channel_info['invite_link']
            
        # Если есть username канала, используем его
        if hasattr(settings, 'required_channel_username') and settings.required_channel_username:
            return f"https://t.me/{settings.required_channel_username.lstrip('@')}"
        
        # Если ничего не получилось, возвращаем None
        logger.warning(f"⚠️ Could not generate valid link for channel {settings.required_channel_id}")
        return None