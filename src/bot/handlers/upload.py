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

logger = logging.getLogger(__name__)
router = Router()

# FSM состояния для загрузки
class UploadStates(StatesGroup):
    waiting_geo = State()
    waiting_custom_geo = State()
    waiting_file = State()
    waiting_notes = State()

def load_custom_geos() -> List[str]:
    """Загрузка пользовательских ГЕО из файла"""
    if os.path.exists(CUSTOM_GEOS_FILE):
        try:
            with open(CUSTOM_GEOS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('custom_geos', [])
        except Exception as e:
            logger.error(f"Error loading custom geos: {e}")
    return []

def save_custom_geos(custom_geos: List[str]) -> bool:
    """Сохранение пользовательских ГЕО в файл"""
    try:
        data = {'custom_geos': custom_geos}
        with open(CUSTOM_GEOS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error saving custom geos: {e}")
        return False

def get_all_geos() -> List[str]:
    """Получение всех доступных ГЕО (стандартные + пользовательские) в алфавитном порядке"""
    custom_geos = load_custom_geos()
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

def generate_creative_id(geo: str) -> str:
    """Генерация ID креатива в формате IDGEOДДММГГNNN"""
    from datetime import datetime
    import random
    
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
    user_info = allowed_users.get(user.id)
    
    if not user_info:
        await message.answer("❌ У вас нет доступа к загрузке креативов.")
        return
    
    await state.set_state(UploadStates.waiting_geo)
    
    # Получаем все ГЕО в алфавитном порядке
    all_geos = get_all_geos()
    keyboard_rows = []
    
    # Разбиваем ГЕО на ряды по 4 кнопки
    for i in range(0, len(all_geos), 4):
        row = []
        for geo in all_geos[i:i+4]:
            # Помечаем пользовательские ГЕО звездочкой
            custom_geos = load_custom_geos()
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
    geo = callback.data.replace("geo_", "")
    
    all_geos = get_all_geos()
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
    all_geos = get_all_geos()
    keyboard_rows = []
    
    for i in range(0, len(all_geos), 4):
        row = []
        for geo in all_geos[i:i+4]:
            custom_geos = load_custom_geos()
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
    await state.set_state(UploadStates.waiting_notes)
    logger.info("State set to waiting_notes")
    
    # Клавиатура для добавления заметок
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Добавить описание", callback_data="add_notes")],
        [InlineKeyboardButton(text="✅ Сохранить без описания", callback_data="save_creative")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="upload_cancel")]
    ])
    
    text = f"""
✅ <b>Файл получен!</b>

🌍 <b>ГЕО:</b> {geo}
📄 <b>Файл:</b> {file_name}
📏 <b>Размер:</b> {file_size / 1024:.0f} КБ
🎯 <b>Тип:</b> {file_ext.upper()}

💬 <b>Хотите добавить описание к креативу?</b>

Описание поможет другим пользователям понять содержание креатива.
"""
    
    logger.info("Sending notes prompt message to user")
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    logger.info(f"User {user.id} uploaded file: {file_name} ({file_size} bytes) - notes prompt sent")

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
    
    # Генерируем ID креатива
    creative_id = generate_creative_id(geo)
    
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
    
    # Получаем информацию о пользователе
    user_info = settings.allowed_users.get(user.id, {})
    buyer_id = user_info.get('buyer_id', '')
    
    await callback.message.edit_text("⏳ <b>Сохраняем креатив...</b>", parse_mode="HTML")
    
    try:
        # Скачиваем файл с Telegram
        bot_instance = callback.bot
        file_info = await bot_instance.get_file(telegram_file_id)
        file_io = await bot_instance.download_file(file_info.file_path)  # Получаем io.BytesIO
        file_bytes = file_io.read()  # Читаем реальные байты из потока
        
        # Пробуем загрузить в Google Drive, fallback к временным ссылкам
        try:
            from integrations.google.drive import GoogleDriveService
            
            google_drive = GoogleDriveService()
            file_id, web_view_link, sha256_hash_gdrive = await google_drive.upload_file(
                file_content=file_bytes,
                filename=file_name,
                geo=geo,
                mime_type=mime_type
            )
            
            drive_result = {
                'file_id': file_id,
                'web_view_link': web_view_link
            }
            logger.info(f"File uploaded to Google Drive successfully: {file_id}")
            logger.info(f"Google Drive folder ID: {google_drive.root_folder_id}")
            
        except Exception as gdrive_error:
            logger.warning(f"Google Drive upload failed: {gdrive_error}")
            logger.info("Falling back to temporary links for debugging")
            
            # Fallback: создаем временные ссылки и локальный hash
            import hashlib
            sha256_hash_gdrive = hashlib.sha256(file_bytes).hexdigest()
            
            drive_result = {
                'file_id': f"temp_drive_id_{creative_id}",
                'web_view_link': f"https://drive.google.com/file/d/temp_{creative_id}/view"
            }
        
        # Создаем/находим пользователя в базе данных
        from db.models.user import User
        from db.models.creative import Creative
        from db.database import get_db_session
        from sqlalchemy import select
        
        # Используем hash файла от Google Drive (уже рассчитан)
        sha256_hash = sha256_hash_gdrive
        
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
                drive_file_id=drive_result['file_id'],
                drive_link=drive_result['web_view_link'],
                uploader_user_id=db_user.id,
                uploader_buyer_id=buyer_id or None,
                original_name=file_name,
                ext=file_name.split('.')[-1].lower() if '.' in file_name else None,
                mime_type=mime_type,
                size_bytes=file_size,
                sha256=sha256_hash,
                upload_dt=datetime.utcnow(),
                notes=notes or None
            )
            
            session.add(creative)
            await session.commit()
        
        logger.info(f"Creative {creative_id} saved successfully for user {user.id} (without Google Drive)")
        
        success_text = f"""
🎉 <b>Креатив успешно сохранен!</b>

🆔 <b>ID креатива:</b> <code>{creative_id}</code>
🌍 <b>ГЕО:</b> {geo}
📄 <b>Файл:</b> {file_name}
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
    all_geos = get_all_geos()
    if geo_code in all_geos:
        await message.answer(
            f"⚠️ <b>ГЕО код {geo_code} уже существует!</b>\n\n"
            f"💡 Выберите другой код или вернитесь к выбору ГЕО.",
            parse_mode="HTML"
        )
        return
    
    # Добавляем новый ГЕО
    custom_geos = load_custom_geos()
    custom_geos.append(geo_code)
    
    if save_custom_geos(custom_geos):
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
        
        logger.info(f"User {message.from_user.id} added custom GEO: {geo_code}")
        
    else:
        await message.answer(
            "❌ <b>Ошибка при сохранении ГЕО!</b>\n\n"
            "🔧 Попробуйте еще раз или обратитесь к администратору.",
            parse_mode="HTML"
        )

@router.callback_query(F.data == "back_to_geo_selection")
async def handle_back_to_geo_selection(callback: CallbackQuery, state: FSMContext):
    """Возврат к выбору ГЕО из добавления нового"""
    await handle_change_geo(callback, state)

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

def generate_creative_id(geo: str) -> str:
    """Генерация уникального ID креатива"""
    now = datetime.now()
    date_str = now.strftime("%d%m%y")
    
    # Простая генерация номера (в реальности должна быть связана с БД)
    sequence = now.strftime("%H%M%S")[-3:]  # Последние 3 цифры времени как номер
    
    return f"ID{geo.upper()}{date_str}{sequence}"