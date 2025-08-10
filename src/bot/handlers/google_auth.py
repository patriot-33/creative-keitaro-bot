"""
Google Drive OAuth authorization handlers for Telegram bot
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
import aiohttp

import sys
from pathlib import Path

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from core.config import settings
from db.database import get_db_session
from db.models.user import User
from sqlalchemy import select

logger = logging.getLogger(__name__)
router = Router()

@router.message(Command("google_auth"))
async def cmd_google_auth(message: Message):
    """Command to start Google Drive authorization"""
    user = message.from_user
    
    # Check if user has access
    allowed_users = settings.allowed_users
    user_info = allowed_users.get(user.id)
    
    if not user_info:
        await message.answer("❌ У вас нет доступа к этой функции.")
        return
    
    # Check current authorization status
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{settings.google_oauth_redirect_uri.replace('/auth/google/callback', '')}/auth/google/status",
                params={'user_id': str(user.id)}
            ) as resp:
                if resp.status == 200:
                    status_data = await resp.json()
                    
                    if status_data.get('authorized') and not status_data.get('expired'):
                        await message.answer(
                            "✅ <b>Google Drive уже авторизован!</b>\\n\\n"
                            "🗂 Ваши креативы будут сохраняться в Google Drive.\\n"
                            "📅 Токен действителен до: " + status_data.get('expires_at', 'неизвестно'),
                            parse_mode="HTML"
                        )
                        return
    except Exception as e:
        logger.warning(f"Could not check auth status: {e}")
    
    # Start authorization process
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔐 Авторизовать Google Drive", callback_data=f"start_google_auth_{user.id}")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_auth")]
    ])
    
    text = f"""
🔐 <b>Авторизация Google Drive</b>

👋 Привет, {user.first_name}!

📁 Для сохранения креативов в Google Drive необходимо предоставить доступ к вашему аккаунту.

🔒 <b>Безопасность:</b>
• Доступ только к Google Drive
• Токены шифруются и хранятся безопасно  
• Можно отозвать в любое время в настройках Google

⚡ <b>Преимущества:</b>
• Креативы сохраняются в ваш Google Drive
• Рабочие ссылки для просмотра файлов
• Автоматическая организация по папкам GEO

Нажмите кнопку ниже для начала авторизации.
"""
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    logger.info(f"User {user.id} requested Google Drive authorization")

@router.callback_query(F.data.startswith("start_google_auth_"))
async def handle_start_google_auth(callback: CallbackQuery):
    """Handle Google OAuth start"""
    user_id = callback.data.split("_")[-1]
    
    if str(callback.from_user.id) != user_id:
        await callback.answer("❌ Ошибка авторизации", show_alert=True)
        return
    
    try:
        # Request auth URL from OAuth server
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{settings.google_oauth_redirect_uri.replace('/auth/google/callback', '')}/auth/google/start",
                params={'user_id': user_id}
            ) as resp:
                if resp.status == 200:
                    auth_data = await resp.json()
                    auth_url = auth_data['auth_url']
                    
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔐 Открыть авторизацию", url=auth_url)],
                        [InlineKeyboardButton(text="🔄 Проверить статус", callback_data=f"check_auth_status_{user_id}")],
                        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_auth")]
                    ])
                    
                    text = f"""
🔐 <b>Авторизация Google Drive</b>

✅ Ссылка для авторизации создана!

🌐 <b>Инструкция:</b>
1. Нажмите кнопку "🔐 Открыть авторизацию"
2. Войдите в ваш Google аккаунт
3. Разрешите доступ к Google Drive
4. Вернитесь сюда и нажмите "🔄 Проверить статус"

⚠️ <b>Важно:</b>
Ссылка откроется в браузере. После успешной авторизации можете закрыть браузер.
"""
                    
                    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
                    await callback.answer("✅ Ссылка создана!")
                    
                else:
                    error_data = await resp.json()
                    await callback.message.edit_text(
                        f"❌ <b>Ошибка создания авторизации</b>\\n\\n"
                        f"🔧 Детали: {error_data.get('error', 'Unknown error')}",
                        parse_mode="HTML"
                    )
                    await callback.answer("❌ Ошибка")
                    
    except Exception as e:
        logger.error(f"Error starting Google auth: {e}")
        await callback.message.edit_text(
            "❌ <b>Ошибка авторизации</b>\\n\\n"
            "🔧 Попробуйте позже или обратитесь к администратору.",
            parse_mode="HTML"
        )
        await callback.answer("❌ Ошибка сервера")

@router.callback_query(F.data.startswith("check_auth_status_"))
async def handle_check_auth_status(callback: CallbackQuery):
    """Check Google OAuth status"""
    user_id = callback.data.split("_")[-1]
    
    if str(callback.from_user.id) != user_id:
        await callback.answer("❌ Ошибка авторизации", show_alert=True)
        return
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{settings.google_oauth_redirect_uri.replace('/auth/google/callback', '')}/auth/google/status",
                params={'user_id': user_id}
            ) as resp:
                if resp.status == 200:
                    status_data = await resp.json()
                    
                    if status_data.get('authorized') and not status_data.get('expired'):
                        # Successfully authorized
                        await callback.message.edit_text(
                            "✅ <b>Google Drive успешно авторизован!</b>\\n\\n"
                            "🗂 Теперь ваши креативы будут сохраняться в Google Drive\\n"
                            f"📅 Токен действителен до: {status_data.get('expires_at', 'неизвестно')}\\n\\n"
                            "💡 Можете загружать креативы через /upload",
                            parse_mode="HTML"
                        )
                        await callback.answer("✅ Авторизация завершена!")
                        
                    else:
                        # Not yet authorized
                        await callback.answer("⏳ Авторизация еще не завершена", show_alert=True)
                        
                else:
                    await callback.answer("❌ Ошибка проверки статуса", show_alert=True)
                    
    except Exception as e:
        logger.error(f"Error checking auth status: {e}")
        await callback.answer("❌ Ошибка сервера", show_alert=True)

@router.callback_query(F.data == "cancel_auth")
async def handle_cancel_auth(callback: CallbackQuery):
    """Cancel Google OAuth"""
    await callback.message.edit_text(
        "❌ <b>Авторизация отменена</b>\\n\\n"
        "💡 Для авторизации Google Drive используйте: /google_auth",
        parse_mode="HTML"
    )
    await callback.answer("❌ Отменено")