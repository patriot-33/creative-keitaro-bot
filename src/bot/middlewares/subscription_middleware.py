"""
Middleware для проверки обязательной подписки на канал
"""

import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.services.subscription_checker import SubscriptionChecker
from core.config import settings

logger = logging.getLogger(__name__)


class SubscriptionMiddleware(BaseMiddleware):
    """Middleware для проверки подписки пользователя на обязательный канал"""

    def __init__(self):
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        
        # Пропускаем проверку если канал не настроен
        if not settings.required_channel_id:
            return await handler(event, data)
        
        # Получаем пользователя
        user = event.from_user
        if not user:
            return await handler(event, data)
            
        # Пропускаем проверку для команды /start
        if isinstance(event, Message) and event.text and event.text.startswith('/start'):
            return await handler(event, data)
            
        # Пропускаем проверку для callback'ов связанных с подпиской
        if isinstance(event, CallbackQuery) and event.data and event.data.startswith('check_subscription'):
            return await handler(event, data)
        
        # Проверяем подписку только для команд загрузки
        should_check = False
        if isinstance(event, Message):
            if event.text and event.text.startswith('/upload'):
                should_check = True
        elif isinstance(event, CallbackQuery):
            if event.data and ('geo_' in event.data or 'upload' in event.data):
                should_check = True
                
        if not should_check:
            return await handler(event, data)
        
        # Получаем бот из данных
        bot = data.get('bot')
        if not bot:
            return await handler(event, data)
        
        # Проверяем подписку
        is_subscribed = await SubscriptionChecker.is_user_subscribed(bot, user.id)
        
        if not is_subscribed:
            # Получаем информацию о канале
            channel_info = await SubscriptionChecker.get_channel_info(bot)
            channel_link = SubscriptionChecker.get_channel_link()
            
            # Формируем сообщение о необходимости подписки
            channel_name = channel_info.get('title', 'Канал') if channel_info else 'Канал'
            
            text = f"""
🔒 <b>Требуется подписка на канал</b>

Для загрузки креативов необходимо подписаться на наш канал:
📢 <b>{channel_name}</b>

После подписки нажмите кнопку "Проверить подписку" для продолжения.
"""
            
            # Создаем клавиатуру
            buttons = []
            
            if channel_link:
                buttons.append([InlineKeyboardButton(
                    text="📢 Подписаться на канал",
                    url=channel_link
                )])
            
            buttons.append([InlineKeyboardButton(
                text="🔄 Проверить подписку",
                callback_data="check_subscription"
            )])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            
            if isinstance(event, Message):
                await event.answer(text, reply_markup=keyboard, parse_mode="HTML")
            elif isinstance(event, CallbackQuery):
                await event.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
                await event.answer("Требуется подписка на канал", show_alert=True)
            
            return  # Прерываем выполнение handler'а
        
        # Если подписка есть, продолжаем выполнение
        return await handler(event, data)