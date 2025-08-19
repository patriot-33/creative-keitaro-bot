"""
Обработчики для загрузки креативов
"""

import logging
from typing import Dict, Any, List, Optional
import os
import json
from datetime import datetime
import hashlib
import mimetypes

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, ContentType
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from core.config import settings
from bot.services.custom_geos import CustomGeosService

logger = logging.getLogger(__name__)
router = Router()

# FSM состояния для загрузки
class UploadStates(StatesGroup):
    waiting_geo = State()
    waiting_custom_geo = State()
    waiting_file = State()
    choosing_naming = State()  # Новое состояние: выбор типа названия
    waiting_custom_name = State()  # Новое состояние: ввод пользовательского названия
    waiting_notes = State()

async def load_custom_geos() -> List[str]:
    """Загрузка пользовательских ГЕО из базы данных"""
    try:
        custom_geos = await CustomGeosService.get_all_custom_geos()
        logger.error(f"🔄 CUSTOM GEOS: Loaded {len(custom_geos)} from database: {custom_geos}")
        return custom_geos
    except Exception as e:
        logger.error(f"❌ CUSTOM GEOS: Error loading from database: {e}")
        return []

async def save_custom_geo(geo_code: str) -> bool:
    """Сохранение нового пользовательского ГЕО в базу данных"""
    try:
        logger.error(f"💾 CUSTOM GEOS DB: Attempting to save geo code: {geo_code}")
        result = await CustomGeosService.add_custom_geo(geo_code)
        
        if result:
            logger.error(f"✅ CUSTOM GEOS DB: Successfully saved geo code: {geo_code}")
        else:
            logger.error(f"❌ CUSTOM GEOS DB: Failed to save geo code: {geo_code}")
            
        return result
    except Exception as e:
        logger.error(f"❌ CUSTOM GEOS DB: Exception saving geo code {geo_code}: {e}")
        return False

async def get_all_geos() -> List[str]:
    """Получение всех доступных ГЕО (стандартные + пользовательские) в алфавитном порядке"""
    custom_geos = await load_custom_geos()
    all_geos = list(set(SUPPORTED_GEOS + custom_geos))  # Убираем дубликаты
    return sorted(all_geos)  # Сортируем по алфавиту

# Поддерживаемые ГЕО
SUPPORTED_GEOS = [
    "AT", "AZ", "BE", "BG", "CH", "CZ", "DE", "ES", "FR", "HR", 
    "HU", "IT", "NL", "PL", "RO", "SI", "SK", "TR", "UK", "US"
]

# Файл для хранения пользовательских ГЕО
CUSTOM_GEOS_FILE = "data/custom_geos.json"

# Поддерживаемые типы файлов
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.mp4', '.mov', '.gif', '.webp'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

def generate_creative_id(geo: str, buyer_id: str = None, custom_name: str = None) -> str:
    """Генерация ID креатива: пользовательское название или автогенерация
    
    Args:
        geo: Код географии (US, TR, AZ и т.д.)
        buyer_id: ID байера пользователя (v1, n1, и т.д.)
        custom_name: Пользовательское название (tr12, test24 и т.д.)
    
    Returns:
        str: Итоговый creative_id
        
    Examples:
        Пользовательское: generate_creative_id("US", "v1", "tr12") -> "v1tr12"
        Автогенерация: generate_creative_id("US") -> "IDUS131225001"
    """
    import re
    from datetime import datetime
    import random
    
    # Если есть buyer_id и custom_name - создаем пользовательское название
    if buyer_id and buyer_id.strip() and custom_name and custom_name.strip():
        # Нормализация: приводим к lowercase
        normalized_buyer = buyer_id.lower().strip()
        normalized_name = custom_name.lower().strip()
        
        # Валидация символов: только латиница и цифры
        if not re.match(r'^[a-z0-9]+$', normalized_buyer):
            raise ValueError(f"Buyer ID содержит недопустимые символы: {buyer_id}")
        if not re.match(r'^[a-z0-9]+$', normalized_name):
            raise ValueError(f"Название содержит недопустимые символы: {custom_name}")
        
        # Создаем итоговый ID
        result = f"{normalized_buyer}{normalized_name}"
        
        # Проверка длины (безопасный лимит)
        if len(result) > 25:
            raise ValueError(f"Название слишком длинное: {len(result)} символов (макс. 25)")
        
        # Проверка на запрещенные значения
        forbidden_values = ['null', 'unknown', 'empty']
        if result in forbidden_values:
            raise ValueError(f"Запрещенное название: {result}")
            
        return result
    
    # Автогенерация в стандартном формате
    now = datetime.now()
    date_part = now.strftime('%d%m%y')  # ДДММГГ
    sequence = random.randint(1, 999)   # Случайный номер 001-999
    
    return f"ID{geo.upper()}{date_part}{sequence:03d}"

@router.message(Command("upload"))
async def cmd_upload(message: Message, state: FSMContext):
    """Команда для начала загрузки креатива"""
    user = message.from_user
    
    # Проверка доступа
    allowed_users = settings.allowed_users
    user_info = allowed_users.get(user.id) or allowed_users.get(str(user.id))
    
    if not user_info:
        await message.answer("❌ У вас нет доступа к загрузке креативов.")
        return
    
    # Проверка подписки на обязательный канал
    from bot.services.subscription_checker import SubscriptionChecker
    
    logger.info(f"🔒 SUBSCRIPTION CHECK: Channel ID = {settings.required_channel_id}")
    
    if settings.required_channel_id:
        logger.info(f"🔍 SUBSCRIPTION: Checking subscription for user {user.id} to channel {settings.required_channel_id}")
        is_subscribed = await SubscriptionChecker.is_user_subscribed(message.bot, user.id)
        
        if not is_subscribed:
            logger.info(f"❌ SUBSCRIPTION: User {user.id} is NOT subscribed to channel {settings.required_channel_id}")
            
            # Получаем информацию о канале
            channel_info = await SubscriptionChecker.get_channel_info(message.bot)
            channel_link = SubscriptionChecker.get_channel_link()
            
            channel_name = channel_info.get('title', 'Канал') if channel_info else 'Канал'
            
            text = f"""
🔒 <b>Требуется подписка на канал</b>

Для загрузки креативов необходимо подписаться на наш канал:
📢 <b>{channel_name}</b>

После подписки нажмите кнопку "Проверить подписку" для продолжения.
"""
            
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
            
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
            return
        else:
            logger.info(f"✅ SUBSCRIPTION: User {user.id} is subscribed to channel {settings.required_channel_id}")
    else:
        logger.info("🔒 SUBSCRIPTION: No required channel configured, skipping check")
    
    await state.set_state(UploadStates.waiting_geo)
    
    # Получаем все ГЕО в алфавитном порядке
    all_geos = await get_all_geos()
    custom_geos = await load_custom_geos()
    keyboard_rows = []
    
    # Разбиваем ГЕО на ряды по 4 кнопки
    for i in range(0, len(all_geos), 4):
        row = []
        for geo in all_geos[i:i+4]:
            # Помечаем пользовательские ГЕО звездочкой
            if geo in custom_geos:
                row.append(InlineKeyboardButton(text=f"⭐ {geo}", callback_data=f"geo_{geo}"))
            else:
                row.append(InlineKeyboardButton(text=f"🌍 {geo}", callback_data=f"geo_{geo}"))
        keyboard_rows.append(row)
    
    # Добавляем кнопку для добавления нового ГЕО и отмены
    keyboard_rows.append([InlineKeyboardButton(text="➕ Добавить ГЕО", callback_data="add_custom_geo")])
    keyboard_rows.append([InlineKeyboardButton(text="❌ Отменить", callback_data="upload_cancel")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    text = f"""
📤 <b>Загрузка креатива</b>

👋 Привет, {user.first_name}!

🌍 <b>Выберите географический регион для креатива:</b>

⭐ - пользовательские ГЕО
🌍 - стандартные ГЕО

💡 <b>Поддерживаемые форматы файлов:</b>
• Изображения: JPG, PNG, GIF, WEBP
• Видео: MP4, MOV
• Максимальный размер: 50 МБ

🎯 <b>После выбора ГЕО вы сможете загрузить файл</b>
"""
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    logger.info(f"User {user.id} started upload process")

@router.callback_query(F.data.startswith("geo_"))
async def handle_geo_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора ГЕО"""
    user = callback.from_user
    
    # Дополнительная проверка подписки
    from bot.services.subscription_checker import SubscriptionChecker
    
    if settings.required_channel_id:
        logger.info(f"🔍 SUBSCRIPTION CALLBACK: Checking subscription for user {user.id} to channel {settings.required_channel_id}")
        is_subscribed = await SubscriptionChecker.is_user_subscribed(callback.bot, user.id)
        
        if not is_subscribed:
            logger.info(f"❌ SUBSCRIPTION CALLBACK: User {user.id} is NOT subscribed to channel {settings.required_channel_id}")
            await callback.answer("❌ Требуется подписка на канал", show_alert=True)
            
            # Показываем сообщение о подписке
            channel_info = await SubscriptionChecker.get_channel_info(callback.bot)
            channel_link = SubscriptionChecker.get_channel_link()
            
            channel_name = channel_info.get('title', 'Канал') if channel_info else 'Канал'
            
            text = f"""
🔒 <b>Требуется подписка на канал</b>

Для загрузки креативов необходимо подписаться на наш канал:
📢 <b>{channel_name}</b>

После подписки нажмите кнопку "Проверить подписку" для продолжения.
"""
            
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
            
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            return
    
    geo = callback.data.replace("geo_", "")
    
    all_geos = await get_all_geos()
    if geo not in all_geos:
        await callback.answer("❌ Неподдерживаемое ГЕО!", show_alert=True)
        return
    
    await state.update_data(geo=geo)
    await state.set_state(UploadStates.waiting_file)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Изменить ГЕО", callback_data="change_geo")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="upload_cancel")]
    ])
    
    text = f"""
📁 <b>Загрузка файла</b>

🌍 <b>Выбранное ГЕО:</b> {geo}

📎 <b>Теперь отправьте файл креатива:</b>

✅ <b>Поддерживаемые форматы:</b>
• 🖼 Изображения: JPG, PNG, GIF, WEBP
• 🎬 Видео: MP4, MOV

📏 <b>Ограничения:</b>
• Максимальный размер: 50 МБ
• Только один файл за раз

💡 <b>Просто перетащите файл в чат или нажмите скрепку и выберите файл</b>
"""
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer(f"✅ Выбрано ГЕО: {geo}")

@router.callback_query(F.data == "change_geo")
async def handle_change_geo(callback: CallbackQuery, state: FSMContext):
    """Изменение выбранного ГЕО"""
    await state.set_state(UploadStates.waiting_geo)
    
    # Повторно показываем клавиатуру с ГЕО
    all_geos = await get_all_geos()
    custom_geos = await load_custom_geos()
    keyboard_rows = []
    
    for i in range(0, len(all_geos), 4):
        row = []
        for geo in all_geos[i:i+4]:
            if geo in custom_geos:
                row.append(InlineKeyboardButton(text=f"⭐ {geo}", callback_data=f"geo_{geo}"))
            else:
                row.append(InlineKeyboardButton(text=f"🌍 {geo}", callback_data=f"geo_{geo}"))
        keyboard_rows.append(row)
    
    keyboard_rows.append([InlineKeyboardButton(text="➕ Добавить ГЕО", callback_data="add_custom_geo")])
    keyboard_rows.append([InlineKeyboardButton(text="❌ Отменить", callback_data="upload_cancel")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    text = """
🌍 <b>Выбор ГЕО</b>

⭐ - пользовательские ГЕО
🌍 - стандартные ГЕО

Выберите географический регион для креатива:
"""
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.message(UploadStates.waiting_file)
async def handle_file_upload(message: Message, state: FSMContext):
    """Обработка загруженного файла"""
    user = message.from_user
    
    # Проверяем, что отправлен файл
    if not (message.photo or message.video or message.document or message.animation):
        await message.answer(
            "❌ <b>Файл не обнаружен!</b>\n\n"
            "📎 Пожалуйста, отправьте файл креатива.\n"
            "✅ Поддерживаемые форматы: JPG, PNG, GIF, WEBP, MP4, MOV",
            parse_mode="HTML"
        )
        return
    
    # Определяем тип файла и получаем file_id
    file_obj = None
    file_name = None
    file_size = 0
    
    if message.photo:
        # Берем фото наибольшего размера
        file_obj = message.photo[-1]
        file_name = f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        file_size = file_obj.file_size or 0
    elif message.video:
        file_obj = message.video
        file_name = message.video.file_name or f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        file_size = message.video.file_size or 0
    elif message.animation:
        file_obj = message.animation  
        file_name = message.animation.file_name or f"animation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.gif"
        file_size = message.animation.file_size or 0
    elif message.document:
        file_obj = message.document
        file_name = message.document.file_name or f"document_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        file_size = message.document.file_size or 0
    
    # Проверка размера файла
    if file_size > MAX_FILE_SIZE:
        await message.answer(
            f"❌ <b>Файл слишком большой!</b>\n\n"
            f"📏 Размер файла: {file_size / 1024 / 1024:.1f} МБ\n"
            f"📏 Максимальный размер: {MAX_FILE_SIZE / 1024 / 1024:.0f} МБ\n\n"
            f"💡 Сожмите файл или выберите другой файл.",
            parse_mode="HTML"
        )
        return
    
    # Определяем расширение файла
    if file_name:
        file_ext = os.path.splitext(file_name.lower())[1] if '.' in file_name else '.unknown'
    else:
        file_ext = '.unknown'
    
    # Проверка расширения файла
    if file_ext not in ALLOWED_EXTENSIONS and file_ext != '.unknown':
        await message.answer(
            f"❌ <b>Неподдерживаемый формат файла!</b>\n\n"
            f"📄 Ваш файл: {file_ext}\n\n"
            f"✅ Поддерживаемые форматы:\n"
            f"• Изображения: {', '.join([ext for ext in ALLOWED_EXTENSIONS if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']])}\n"
            f"• Видео: {', '.join([ext for ext in ALLOWED_EXTENSIONS if ext in ['.mp4', '.mov']])}\n\n"
            f"💡 Пожалуйста, загрузите файл в поддерживаемом формате.",
            parse_mode="HTML"
        )
        return
    
    # Сохраняем информацию о файле
    user_data = await state.get_data()
    geo = user_data.get('geo')
    
    await state.update_data(
        file_id=file_obj.file_unique_id,
        telegram_file_id=file_obj.file_id,
        file_name=file_name,
        file_size=file_size,
        file_ext=file_ext
    )
    
    logger.info(f"File processed: {file_name}, size: {file_size}, ext: {file_ext}, geo: {geo}")
    await state.set_state(UploadStates.choosing_naming)
    logger.info("State set to choosing_naming")
    
    # Клавиатура для выбора типа названия
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Задать своё название", callback_data="custom_naming")],
        [InlineKeyboardButton(text="🤖 Автоматическое название", callback_data="auto_naming")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="upload_cancel")]
    ])
    
    text = f"""
✅ <b>Файл получен!</b>

🌍 <b>ГЕО:</b> {geo}
📄 <b>Файл:</b> {file_name}
📏 <b>Размер:</b> {file_size / 1024:.0f} КБ
🎯 <b>Тип:</b> {file_ext.upper()}

🎯 <b>Выберите тип названия креатива:</b>

📝 <b>Своё название</b> - вы задаете уникальное имя (например: tr12)
🤖 <b>Автоматическое</b> - система сгенерирует стандартное название

💡 <b>Пользовательские названия</b> будут иметь формат: <code>ваш_buyer_id + название</code>
"""
    
    logger.info("Sending notes prompt message to user")
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    logger.info(f"User {user.id} uploaded file: {file_name} ({file_size} bytes) - notes prompt sent")

@router.callback_query(F.data == "custom_naming")
async def handle_custom_naming(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора пользовательского названия"""
    await state.set_state(UploadStates.waiting_custom_name)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Автоматическое название", callback_data="auto_naming")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="upload_cancel")]
    ])
    
    text = """
📝 <b>Пользовательское название</b>

✍️ <b>Введите своё название креатива:</b>

📋 <b>Требования:</b>
• Только латинские буквы и цифры
• Длина: 2-20 символов
• Пример: tr12, test24, promo1

💡 <b>Итоговое название будет:</b> <code>ваш_buyer_id + название</code>
"""
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "auto_naming")
async def handle_auto_naming(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора автоматического названия"""
    await state.set_state(UploadStates.waiting_notes)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Добавить описание", callback_data="add_notes")],
        [InlineKeyboardButton(text="💾 Сохранить без описания", callback_data="save_creative")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="upload_cancel")]
    ])
    
    text = """
🤖 <b>Автоматическое название выбрано!</b>

📋 <b>Система сгенерирует стандартное название в формате:</b>
<code>IDГEOДДММГГNNN</code>

💬 <b>Хотите добавить описание к креативу?</b>

💡 Описание поможет лучше идентифицировать креатив в отчетах
"""
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.message(UploadStates.waiting_custom_name)
async def handle_custom_name_input(message: Message, state: FSMContext):
    """Обработка ввода пользовательского названия"""
    import re
    from sqlalchemy import select
    from db.models.creative import Creative
    from db.database import get_db_session
    
    user = message.from_user
    custom_name = message.text.strip()
    
    # Валидация
    if len(custom_name) < 2 or len(custom_name) > 20:
        await message.answer(
            "❌ <b>Некорректная длина!</b>\n\n"
            "📏 Название должно содержать от 2 до 20 символов\n"
            "📝 Попробуйте еще раз:",
            parse_mode="HTML"
        )
        return
    
    if not re.match(r'^[a-zA-Z0-9]+$', custom_name):
        await message.answer(
            "❌ <b>Недопустимые символы!</b>\n\n"
            "✅ Разрешены только латинские буквы и цифры\n"
            "💡 Примеры: tr12, test24, promo1\n"
            "📝 Попробуйте еще раз:",
            parse_mode="HTML"
        )
        return
    
    # Получаем buyer_id пользователя
    user_info = settings.allowed_users.get(user.id, {}) or settings.allowed_users.get(str(user.id), {})
    buyer_id = user_info.get('buyer_id', '')
    
    if not buyer_id:
        await message.answer(
            "❌ <b>Buyer ID не найден!</b>\n\n"
            "🔧 Обратитесь к администратору для настройки профиля\n"
            "💡 Пока используется автоматическое название",
            parse_mode="HTML"
        )
        await state.set_state(UploadStates.waiting_notes)
        return
    
    # Проверяем уникальность в рамках buyer_id
    try:
        user_data = await state.get_data()
        geo = user_data.get('geo')
        
        # Генерируем итоговый creative_id
        final_creative_id = generate_creative_id(geo, buyer_id, custom_name)
        
        # Проверяем уникальность в базе
        async with get_db_session() as session:
            stmt = select(Creative).where(Creative.creative_id == final_creative_id)
            existing = await session.execute(stmt)
            if existing.scalar_one_or_none():
                await message.answer(
                    f"❌ <b>Название уже используется!</b>\n\n"
                    f"🆔 Креатив с ID <code>{final_creative_id}</code> уже существует\n"
                    f"📝 Выберите другое название:",
                    parse_mode="HTML"
                )
                return
        
        # Сохраняем пользовательское название
        await state.update_data(custom_name=custom_name)
        await state.set_state(UploadStates.waiting_notes)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Добавить описание", callback_data="add_notes")],
            [InlineKeyboardButton(text="💾 Сохранить без описания", callback_data="save_creative")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="upload_cancel")]
        ])
        
        text = f"""
✅ <b>Название принято!</b>

🆔 <b>ID креатива:</b> <code>{final_creative_id}</code>
📝 <b>Ваше название:</b> {custom_name}
👤 <b>Buyer ID:</b> {buyer_id}

💬 <b>Хотите добавить описание к креативу?</b>

💡 Описание поможет лучше идентифицировать креатив в отчетах
"""
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        
    except ValueError as e:
        await message.answer(
            f"❌ <b>Ошибка валидации:</b>\n{str(e)}\n\n📝 Попробуйте другое название:",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error processing custom name: {e}")
        await message.answer(
            "❌ <b>Системная ошибка!</b>\n\n🔧 Попробуйте еще раз или обратитесь к администратору",
            parse_mode="HTML"
        )

@router.callback_query(F.data == "add_notes")
async def handle_add_notes(callback: CallbackQuery, state: FSMContext):
    """Запрос описания креатива"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="save_creative")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="upload_cancel")]
    ])
    
    text = """
💬 <b>Добавление описания</b>

✍️ <b>Отправьте описание креатива текстовым сообщением:</b>

💡 <b>Примеры хороших описаний:</b>
• "Баннер с промо акцией 50% скидки"
• "Видео креатив для Facebook, вертикальная ориентация"
• "Тестовый креатив для аудитории 25-35 лет"

📝 Описание должно быть не длиннее 500 символов.
"""
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.message(UploadStates.waiting_notes)
async def handle_notes_input(message: Message, state: FSMContext):
    """Обработка введенного описания"""
    notes = message.text
    
    if len(notes) > 500:
        await message.answer(
            "❌ <b>Описание слишком длинное!</b>\n\n"
            f"📏 Ваше описание: {len(notes)} символов\n"
            f"📏 Максимально: 500 символов\n\n"
            f"✂️ Пожалуйста, сократите описание.",
            parse_mode="HTML"
        )
        return
    
    await state.update_data(notes=notes)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Сохранить креатив", callback_data="save_creative")],
        [InlineKeyboardButton(text="✏️ Изменить описание", callback_data="add_notes")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="upload_cancel")]
    ])
    
    text = f"""
📝 <b>Описание добавлено!</b>

💬 <b>Ваше описание:</b>
"{notes}"

✅ Теперь можно сохранить креатив.
"""
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

# ===== НОВЫЕ ОБРАБОТЧИКИ ДЛЯ ПОЛЬЗОВАТЕЛЬСКИХ НАЗВАНИЙ =====

@router.callback_query(F.data == "custom_naming")
async def handle_custom_naming(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора пользовательского названия"""
    user = callback.from_user
    
    # Получаем buyer_id пользователя
    allowed_users = settings.allowed_users
    user_info = allowed_users.get(user.id) or allowed_users.get(str(user.id))
    buyer_id = user_info.get('buyer_id', '') if user_info else ''
    
    # Проверяем есть ли у пользователя buyer_id
    if not buyer_id or not buyer_id.strip():
        await callback.answer("❌ У вас не назначен Buyer ID. Пользовательские названия недоступны.")
        
        # Автоматически переходим к описанию
        await state.set_state(UploadStates.waiting_notes)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Добавить описание", callback_data="add_notes")],
            [InlineKeyboardButton(text="✅ Сохранить без описания", callback_data="save_creative")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="upload_cancel")]
        ])
        
        text = """
⚠️ <b>Buyer ID не найден</b>

Пользовательские названия доступны только пользователям с назначенным Buyer ID.
Будет использовано автоматическое название.

💬 <b>Хотите добавить описание к креативу?</b>
"""
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        return
    
    # Переходим к вводу названия
    await state.set_state(UploadStates.waiting_custom_name)
    await state.update_data(buyer_id=buyer_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Использовать автоматическое", callback_data="auto_naming")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="upload_cancel")]
    ])
    
    text = f"""
📝 <b>Пользовательское название</b>

👤 <b>Ваш Buyer ID:</b> <code>{buyer_id}</code>

✍️ <b>Введите название креатива (2-20 символов):</b>

📋 <b>Правила:</b>
• Только латинские буквы (a-z) и цифры (0-9)
• Длина: 2-20 символов
• Без пробелов и специальных символов

💡 <b>Примеры:</b> tr12, test24, promo01

🎯 <b>Итоговое название будет:</b> <code>{buyer_id}ваше_название</code>
"""
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "auto_naming") 
async def handle_auto_naming(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора автоматического названия"""
    # Переходим к добавлению описания
    await state.set_state(UploadStates.waiting_notes)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Добавить описание", callback_data="add_notes")],
        [InlineKeyboardButton(text="✅ Сохранить без описания", callback_data="save_creative")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="upload_cancel")]
    ])
    
    text = """
🤖 <b>Автоматическое название выбрано</b>

Система сгенерирует уникальное название в стандартном формате.

💬 <b>Хотите добавить описание к креативу?</b>

Описание поможет другим пользователям понять содержание креатива.
"""
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.message(UploadStates.waiting_custom_name)
async def handle_custom_name_input(message: Message, state: FSMContext):
    """Обработка ввода пользовательского названия"""
    import re
    from bot.services.creatives import CreativesService
    
    custom_name = message.text.strip()
    user_data = await state.get_data()
    buyer_id = user_data.get('buyer_id', '')
    
    # Валидация длины
    if len(custom_name) < 2 or len(custom_name) > 20:
        await message.answer(
            "❌ <b>Неверная длина названия!</b>\n\n"
            f"📏 Ваше название: {len(custom_name)} символов\n"
            f"📏 Требуется: 2-20 символов\n\n"
            f"✍️ Попробуйте ещё раз:",
            parse_mode="HTML"
        )
        return
    
    # Валидация символов
    if not re.match(r'^[a-zA-Z0-9]+$', custom_name):
        await message.answer(
            "❌ <b>Недопустимые символы!</b>\n\n"
            f"📝 Ваше название: <code>{custom_name}</code>\n"
            f"✅ Разрешены: латинские буквы (a-z) и цифры (0-9)\n"
            f"❌ Запрещены: пробелы, русские буквы, спецсимволы\n\n"
            f"✍️ Попробуйте ещё раз:",
            parse_mode="HTML"
        )
        return
    
    # Генерируем итоговый ID для проверки уникальности
    try:
        potential_id = generate_creative_id("", buyer_id, custom_name)
    except ValueError as e:
        await message.answer(
            f"❌ <b>Ошибка названия:</b>\n\n{e}\n\n✍️ Попробуйте другое название:",
            parse_mode="HTML"
        )
        return
    
    # Проверяем уникальность в рамках buyer_id  
    existing_creative = await CreativesService.get_creative_by_id(potential_id)
    if existing_creative:
        await message.answer(
            f"❌ <b>Название уже занято!</b>\n\n"
            f"📝 Название <code>{custom_name}</code> уже используется\n"
            f"🎯 Итоговый ID: <code>{potential_id}</code>\n\n"
            f"✍️ Попробуйте другое название:",
            parse_mode="HTML"
        )
        return
    
    # Сохраняем название и переходим к описанию
    await state.update_data(custom_name=custom_name)
    await state.set_state(UploadStates.waiting_notes)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Добавить описание", callback_data="add_notes")],
        [InlineKeyboardButton(text="✅ Сохранить без описания", callback_data="save_creative")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="upload_cancel")]
    ])
    
    text = f"""
✅ <b>Название принято!</b>

📝 <b>Ваше название:</b> <code>{custom_name}</code>
👤 <b>Buyer ID:</b> <code>{buyer_id}</code>
🎯 <b>Итоговый ID:</b> <code>{potential_id}</code>

💬 <b>Хотите добавить описание к креативу?</b>
"""
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "save_creative")
async def handle_save_creative(callback: CallbackQuery, state: FSMContext):
    """Сохранение креатива"""
    user = callback.from_user
    user_data = await state.get_data()
    
    # Получаем все данные
    geo = user_data.get('geo')
    telegram_file_id = user_data.get('telegram_file_id')
    file_name = user_data.get('file_name')
    file_size = user_data.get('file_size', 0)
    file_ext = user_data.get('file_ext', '.unknown')
    notes = user_data.get('notes', '')
    custom_name = user_data.get('custom_name')
    
    # Получаем информацию о пользователе для buyer_id
    user_info = settings.allowed_users.get(user.id, {}) or settings.allowed_users.get(str(user.id), {})
    buyer_id = user_info.get('buyer_id', '')
    
    # Генерируем ID креатива (с учетом пользовательского названия)
    creative_id = generate_creative_id(geo, buyer_id, custom_name)
    
    # Определяем MIME type
    mime_type = 'application/octet-stream'  # default
    if file_ext.lower() in ['.jpg', '.jpeg']:
        mime_type = 'image/jpeg'
    elif file_ext.lower() == '.png':
        mime_type = 'image/png'
    elif file_ext.lower() == '.mp4':
        mime_type = 'video/mp4'
    elif file_ext.lower() == '.gif':
        mime_type = 'image/gif'
    
    await callback.message.edit_text("⏳ <b>Сохраняем креатив...</b>", parse_mode="HTML")
    
    try:
        # Скачиваем файл с Telegram
        bot_instance = callback.bot
        file_info = await bot_instance.get_file(telegram_file_id)
        file_io = await bot_instance.download_file(file_info.file_path)  # Получаем io.BytesIO
        file_bytes = file_io.read()  # Читаем реальные байты из потока
        
        # Сохраняем файл в Telegram (намного проще чем Google Drive!)
        logger.info(f"Starting Telegram file storage...")
        logger.info(f"File details: name={file_name}, size={file_size} bytes, mime={mime_type}, geo={geo}")
        
        try:
            from integrations.telegram.storage import TelegramStorageService
            
            logger.info("Initializing TelegramStorageService...")
            telegram_storage = TelegramStorageService(callback.bot)
            
            logger.info("Storing creative in Telegram...")
            stored_file_id, message_id, sha256_hash = await telegram_storage.store_creative(
                file_id=telegram_file_id,
                file_name=file_name,
                file_size=file_size,
                mime_type=mime_type,
                creative_id=creative_id,
                geo=geo
            )
            
            # Create display link
            telegram_link = telegram_storage.create_telegram_link(stored_file_id, file_name)
            
            storage_result = {
                'telegram_file_id': stored_file_id,
                'telegram_message_id': message_id,
                'telegram_link': telegram_link,
                'sha256_hash': sha256_hash
            }
            
            logger.info(f"Telegram storage SUCCESS!")
            logger.info(f"  - Telegram File ID: {stored_file_id}")
            logger.info(f"  - Message ID: {message_id}")
            logger.info(f"  - Display Link: {telegram_link}")
            logger.info(f"  - SHA256: {sha256_hash[:16]}...")
            logger.info(f"  - User: {user.first_name} ({user.id})")
            
        except Exception as telegram_error:
            logger.error(f"Telegram storage failed: {telegram_error}")
            # This shouldn't happen with Telegram, but just in case
            import hashlib
            sha256_hash = hashlib.sha256(file_bytes).hexdigest()
            
            storage_result = {
                'telegram_file_id': telegram_file_id,  # Use original file_id as fallback
                'telegram_message_id': None,
                'telegram_link': f"telegram://file/{telegram_file_id}",
                'sha256_hash': sha256_hash
            }
        
        # Создаем/находим пользователя в базе данных
        from db.models.user import User
        from db.models.creative import Creative
        from db.database import get_db_session
        from sqlalchemy import select
        
        # Используем hash файла от Telegram Storage (уже рассчитан)
        sha256_hash = storage_result['sha256_hash']
        
        async with get_db_session() as session:
            # Ищем или создаем пользователя
            user_stmt = select(User).where(User.tg_user_id == user.id)
            db_user = await session.execute(user_stmt)
            db_user = db_user.scalar_one_or_none()
            
            if not db_user:
                # Создаем нового пользователя
                from core.enums import UserRole
                db_user = User(
                    tg_user_id=user.id,
                    tg_username=user.username,
                    full_name=f"{user.first_name or ''} {user.last_name or ''}".strip(),
                    role=UserRole.OWNER,  # Используем enum вместо строки
                    buyer_id=buyer_id or None
                )
                session.add(db_user)
                await session.flush()  # Получаем ID
            
            # Создаем запись о креативе
            creative = Creative(
                creative_id=creative_id,
                geo=geo,
                telegram_file_id=storage_result['telegram_file_id'],
                telegram_message_id=storage_result['telegram_message_id'],
                uploader_user_id=db_user.id,
                uploader_buyer_id=buyer_id or None,
                original_name=file_name,
                ext=file_name.split('.')[-1].lower() if '.' in file_name else None,
                mime_type=mime_type,
                size_bytes=file_size,
                sha256=sha256_hash,
                upload_dt=datetime.utcnow(),
                notes=notes or None,
                custom_name=custom_name or None
            )
            
            session.add(creative)
            await session.commit()
        
        logger.info(f"Creative {creative_id} saved successfully for user {user.id} (using Telegram storage)")
        
        # Дублируем креатив в канал хранения
        try:
            from bot.services.creative_duplicator import CreativeDuplicatorService
            
            # Определяем тип файла для API на основе расширения и MIME type
            file_type = "document"  # по умолчанию
            if mime_type.startswith('image/'):
                if file_ext.lower() == '.gif':
                    file_type = "animation"
                else:
                    file_type = "photo"
            elif mime_type.startswith('video/'):
                file_type = "video"
            
            # Дублируем с повторными попытками
            dup_success, dup_message_id, dup_error = await CreativeDuplicatorService.duplicate_with_retry(
                bot=callback.bot,
                creative_id=creative_id,
                file_id=telegram_file_id,
                file_type=file_type,
                geo=geo,
                uploader_name=user.first_name or "Пользователь",
                uploader_username=user.username,
                uploader_id=user.id,
                buyer_id=buyer_id,
                notes=notes,
                custom_name=custom_name,
                file_name=file_name,
                file_size=file_size
            )
            
            # Обновляем статус дублирования в БД
            if dup_success:
                logger.info(f"✅ Креатив {creative_id} успешно продублирован в канал хранения (message_id: {dup_message_id})")
                
                # Обновляем запись в БД
                async with get_db_session() as session:
                    from sqlalchemy import update
                    stmt = update(Creative).where(Creative.creative_id == creative_id).values(
                        is_duplicated=True,
                        duplicated_at=datetime.utcnow(),
                        duplication_message_id=dup_message_id
                    )
                    await session.execute(stmt)
                    await session.commit()
            else:
                logger.warning(f"⚠️ Не удалось продублировать креатив {creative_id} в creo_storage_bot: {dup_error}")
                
                # Сохраняем ошибку в БД
                async with get_db_session() as session:
                    from sqlalchemy import update
                    stmt = update(Creative).where(Creative.creative_id == creative_id).values(
                        is_duplicated=False,
                        duplication_error=dup_error[:500] if dup_error else None  # Ограничиваем длину ошибки
                    )
                    await session.execute(stmt)
                    await session.commit()
                
        except Exception as dup_error:
            logger.error(f"❌ Ошибка при дублировании креатива {creative_id}: {dup_error}")
            # Не прерываем основной процесс из-за ошибки дублирования
        
        # Формируем информацию о названии
        naming_info = ""
        if custom_name:
            naming_info = f"📝 <b>Пользовательское название:</b> {custom_name}\n"
        else:
            naming_info = f"🤖 <b>Название:</b> автоматическое\n"
        
        success_text = f"""
🎉 <b>Креатив успешно сохранен!</b>

🆔 <b>ID креатива:</b> <code>{creative_id}</code>
🌍 <b>ГЕО:</b> {geo}
{naming_info}📄 <b>Файл:</b> {file_name}
📏 <b>Размер:</b> {file_size / 1024:.0f} КБ
👤 <b>Загружен:</b> {user.first_name}
🏷 <b>Buyer ID:</b> {buyer_id or 'не указан'}
💬 <b>Описание:</b> {notes or 'нет'}

✅ Креатив готов к использованию!

💡 <b>Для загрузки еще одного креатива используйте:</b> /upload
"""
        
        await callback.message.edit_text(success_text, parse_mode="HTML")
        
        logger.info(f"Creative {creative_id} saved successfully by user {user.id}")
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error saving creative: {e}")
        logger.error(f"Full traceback: {error_details}")
        
        error_msg = str(e).replace('<', '&lt;').replace('>', '&gt;')[:100]
        await callback.message.edit_text(
            f"❌ <b>Ошибка при сохранении креатива!</b>\n\n"
            f"🔧 Детали: {error_msg}...\n"
            f"📞 Если проблема повторяется, обратитесь к администратору.\n\n"
            f"💡 Используйте /upload для повторной попытки.",
            parse_mode="HTML"
        )
    
    # Очищаем состояние
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "add_custom_geo")
async def handle_add_custom_geo(callback: CallbackQuery, state: FSMContext):
    """Добавление пользовательского ГЕО"""
    await state.set_state(UploadStates.waiting_custom_geo)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Назад к выбору ГЕО", callback_data="back_to_geo_selection")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="upload_cancel")]
    ])
    
    text = """
➕ <b>Добавление нового ГЕО</b>

📝 <b>Отправьте код ГЕО текстовым сообщением:</b>

💡 <b>Примеры:</b>
• <code>KZ</code> - Казахстан
• <code>BY</code> - Беларусь  
• <code>UA</code> - Украина
• <code>MD</code> - Молдова

✅ <b>Требования:</b>
• Только латинские буквы
• Длина: 2-4 символа
• Только заглавные буквы

⚠️ <b>Код ГЕО будет доступен всем пользователям</b>
"""
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.message(UploadStates.waiting_custom_geo)
async def handle_custom_geo_input(message: Message, state: FSMContext):
    """Обработка введенного пользовательского ГЕО"""
    geo_code = message.text.strip().upper()
    
    # Валидация
    if not geo_code.isalpha() or len(geo_code) < 2 or len(geo_code) > 4:
        await message.answer(
            "❌ <b>Некорректный код ГЕО!</b>\n\n"
            "✅ <b>Требования:</b>\n"
            "• Только латинские буквы\n"
            "• Длина: 2-4 символа\n"
            "• Только заглавные буквы\n\n"
            "💡 <b>Примеры:</b> KZ, BY, UA, MD\n\n"
            "📝 Попробуйте еще раз:",
            parse_mode="HTML"
        )
        return
    
    # Проверяем, не существует ли уже такой ГЕО
    all_geos = await get_all_geos()
    if geo_code in all_geos:
        await message.answer(
            f"⚠️ <b>ГЕО код {geo_code} уже существует!</b>\n\n"
            f"💡 Выберите другой код или вернитесь к выбору ГЕО.",
            parse_mode="HTML"
        )
        return
    
    # Добавляем новый ГЕО
    logger.error(f"🔧 CUSTOM GEO: User {message.from_user.id} attempting to add new GEO: {geo_code}")
    
    if await save_custom_geo(geo_code):
        # Устанавливаем новый ГЕО как выбранный
        await state.update_data(geo=geo_code)
        await state.set_state(UploadStates.waiting_file)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ Изменить ГЕО", callback_data="change_geo")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="upload_cancel")]
        ])
        
        text = f"""
✅ <b>Новый ГЕО добавлен!</b>

⭐ <b>Добавленное ГЕО:</b> {geo_code}
🌍 <b>Выбранное ГЕО:</b> {geo_code}

📎 <b>Теперь отправьте файл креатива:</b>

✅ <b>Поддерживаемые форматы:</b>
• 🖼 Изображения: JPG, PNG, GIF, WEBP
• 🎬 Видео: MP4, MOV

📏 <b>Ограничения:</b>
• Максимальный размер: 50 МБ
• Только один файл за раз

💡 <b>Просто перетащите файл в чат или нажмите скрепку и выберите файл</b>
"""
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        
        logger.error(f"✅ CUSTOM GEO SUCCESS: User {message.from_user.id} successfully added custom GEO: {geo_code}")
        
    else:
        logger.error(f"❌ CUSTOM GEO FAILED: User {message.from_user.id} failed to add custom GEO: {geo_code}")
        await message.answer(
            "❌ <b>Ошибка при сохранении ГЕО!</b>\n\n"
            "🔧 Попробуйте еще раз или обратитесь к администратору.",
            parse_mode="HTML"
        )

@router.callback_query(F.data == "back_to_geo_selection")
async def handle_back_to_geo_selection(callback: CallbackQuery, state: FSMContext):
    """Возврат к выбору ГЕО из добавления нового"""
    await handle_change_geo(callback, state)

@router.callback_query(F.data == "check_subscription")
async def handle_check_subscription(callback: CallbackQuery, state: FSMContext):
    """Проверка подписки пользователя на обязательный канал"""
    from bot.services.subscription_checker import SubscriptionChecker
    
    user = callback.from_user
    
    logger.info(f"🔄 SUBSCRIPTION RECHECK: User {user.id} requested subscription recheck")
    
    # Проверяем подписку
    is_subscribed = await SubscriptionChecker.is_user_subscribed(callback.bot, user.id)
    
    if is_subscribed:
        # Подписка есть - возвращаем к загрузке
        logger.info(f"✅ SUBSCRIPTION RECHECK: User {user.id} subscription confirmed")
        await callback.answer("✅ Подписка подтверждена! Теперь вы можете загружать креативы", show_alert=True)
        
        # Возвращаем пользователя к началу процесса загрузки
        await state.clear()
        
        # Показываем меню выбора ГЕО
        all_geos = await get_all_geos()
        buttons = []
        for i in range(0, len(all_geos), 4):
            row = []
            for geo in all_geos[i:i+4]:
                row.append(InlineKeyboardButton(text=geo, callback_data=f"geo_{geo}"))
            buttons.append(row)
        
        # Кнопка добавления нового ГЕО
        buttons.append([InlineKeyboardButton(text="➕ Добавить новое ГЕО", callback_data="add_custom_geo")])
        buttons.append([InlineKeyboardButton(text="❌ Отменить", callback_data="upload_cancel")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await callback.message.edit_text(
            "🌍 <b>Выберите ГЕО для креатива:</b>\n\n"
            f"📊 Доступно ГЕО: {len(all_geos)}\n\n"
            "💡 Если нужного ГЕО нет в списке, вы можете добавить его самостоятельно.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.set_state(UploadStates.waiting_geo)
        
    else:
        # Подписки нет
        logger.info(f"❌ SUBSCRIPTION RECHECK: User {user.id} subscription NOT found")
        await callback.answer("❌ Подписка не найдена. Пожалуйста, подпишитесь на канал и повторите проверку", show_alert=True)
        
        # Получаем информацию о канале
        channel_info = await SubscriptionChecker.get_channel_info(callback.bot)
        channel_link = SubscriptionChecker.get_channel_link()
        
        channel_name = channel_info.get('title', 'Канал') if channel_info else 'Канал'
        
        text = f"""
🔒 <b>Требуется подписка на канал</b>

Для загрузки креативов необходимо подписаться на наш канал:
📢 <b>{channel_name}</b>

После подписки нажмите кнопку "Проверить подписку" для продолжения.
"""
        
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
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "upload_cancel")
async def handle_upload_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена загрузки"""
    await state.clear()
    
    await callback.message.edit_text(
        "❌ <b>Загрузка креатива отменена</b>\n\n"
        "💡 Для начала новой загрузки используйте: /upload",
        parse_mode="HTML"
    )
    await callback.answer("❌ Загрузка отменена")

