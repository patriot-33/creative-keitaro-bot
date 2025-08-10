"""
Обработчики для управления пользователями (админ-функции)
"""

import logging
from typing import Dict, Any, List
import json
import os
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from core.config import settings
from db.database import get_db_session
from db.models.user import User
from sqlalchemy import select
from core.enums import UserRole

logger = logging.getLogger(__name__)
router = Router()

# Пути к файлам
USERS_FILE = "users.json"
PENDING_FILE = "pending_users.json"

# FSM состояния для регистрации
class RegistrationStates(StatesGroup):
    waiting_role = State()
    waiting_buyer_id = State()
    waiting_confirmation = State()

def load_users() -> Dict[int, Dict[str, Any]]:
    """Загрузка списка пользователей из файла"""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Конвертируем строковые ключи в int
                return {int(k): v for k, v in data.items()}
        except Exception as e:
            logger.error(f"Error loading users file: {e}")
    
    # Возвращаем пользователей из конфига как fallback
    return settings.allowed_users.copy()

def save_users(users: Dict[int, Dict[str, Any]]) -> bool:
    """Сохранение списка пользователей в файл"""
    try:
        # Конвертируем int ключи в строки для JSON
        users_str_keys = {str(k): v for k, v in users.items()}
        
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users_str_keys, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error saving users file: {e}")
        return False

def load_pending_users() -> Dict[int, Dict[str, Any]]:
    """Загрузка заявок на регистрацию"""
    if os.path.exists(PENDING_FILE):
        try:
            with open(PENDING_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {int(k): v for k, v in data.items()}
        except Exception as e:
            logger.error(f"Error loading pending users file: {e}")
    return {}

def save_pending_users(pending: Dict[int, Dict[str, Any]]) -> bool:
    """Сохранение заявок на регистрацию"""
    try:
        pending_str_keys = {str(k): v for k, v in pending.items()}
        with open(PENDING_FILE, 'w', encoding='utf-8') as f:
            json.dump(pending_str_keys, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error saving pending users file: {e}")
        return False

def is_admin(user_id: int) -> bool:
    """Проверка прав администратора"""
    # Используем settings.allowed_users вместо файла для актуальности
    users = settings.allowed_users
    user_info = users.get(user_id, {}) or users.get(str(user_id), {})
    role = user_info.get('role', '')
    logger.info(f"Admin check for user {user_id}: role={role}, is_admin={role in ['owner', 'head']}")
    return role in ['owner', 'head']

def can_approve_user(admin_id: int, target_role: str) -> bool:
    """Проверка прав на апрув пользователя"""
    users = settings.allowed_users
    admin_info = users.get(admin_id, {}) or users.get(str(admin_id), {})
    admin_role = admin_info.get('role', '')
    
    # Owner может апрувить кого угодно
    if admin_role == 'owner':
        return True
    
    # Head и teamlead могут апрувить только buyers
    if admin_role in ['head', 'teamlead'] and target_role == 'buyer':
        return True
    
    return False

def get_admin_list() -> List[int]:
    """Получить список всех админов для уведомлений"""
    users = settings.allowed_users
    admins = []
    for user_id, user_info in users.items():
        if user_info.get('role') in ['owner', 'head', 'teamlead']:
            # Конвертируем user_id в int если это строка
            admin_id = int(user_id) if isinstance(user_id, str) else user_id
            admins.append(admin_id)
    return admins

async def save_user_to_database(user_id: int, user_data: dict, approved_by_id: int = None) -> bool:
    """Сохранение пользователя в базу данных PostgreSQL"""
    try:
        async with get_db_session() as session:
            # Проверяем, существует ли пользователь
            result = await session.execute(select(User).where(User.tg_user_id == user_id))
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                # Обновляем существующего пользователя
                existing_user.role = UserRole(user_data['role'])
                existing_user.buyer_id = user_data.get('buyer_id')
                existing_user.tg_username = user_data.get('username', '')
                existing_user.full_name = user_data.get('first_name', '')
                existing_user.is_active = True
                if approved_by_id:
                    existing_user.created_by_id = approved_by_id
            else:
                # Создаем нового пользователя
                new_user = User(
                    tg_user_id=user_id,
                    tg_username=user_data.get('username', ''),
                    full_name=user_data.get('first_name', ''),
                    role=UserRole(user_data['role']),
                    buyer_id=user_data.get('buyer_id') if user_data.get('buyer_id') else None,
                    is_active=True,
                    created_by_id=approved_by_id
                )
                session.add(new_user)
            
            await session.commit()
            logger.info(f"User {user_id} saved to database with role {user_data['role']}")
            return True
            
    except Exception as e:
        logger.error(f"Failed to save user {user_id} to database: {e}")
        return False

async def sync_settings_with_database():
    """Синхронизация settings.allowed_users с базой данных"""
    try:
        async with get_db_session() as session:
            result = await session.execute(select(User).where(User.is_active == True))
            db_users = result.scalars().all()
            
            # Конвертируем в формат settings
            users = {}
            for user in db_users:
                users[user.tg_user_id] = {
                    'role': user.role.value,
                    'buyer_id': user.buyer_id or '',
                    'username': user.tg_username or '',
                    'first_name': user.full_name or '',
                    'is_approved': user.is_active
                }
            
            settings.allowed_users = users
            logger.info(f"Settings synchronized with {len(users)} users from database")
            
    except Exception as e:
        logger.error(f"Failed to sync settings with database: {e}")

# ===== РЕГИСТРАЦИЯ НОВЫХ ПОЛЬЗОВАТЕЛЕЙ =====

@router.message(Command("register"))
async def cmd_register(message: Message, state: FSMContext):
    """Начало регистрации нового пользователя"""
    user_id = message.from_user.id
    
    # Проверяем, не зарегистрирован ли уже
    users = load_users()
    if user_id in users:
        await message.answer("✅ Вы уже зарегистрированы в системе!")
        return
    
    # Проверяем, нет ли уже заявки
    pending = load_pending_users()
    if user_id in pending:
        await message.answer(
            "⏳ Ваша заявка уже отправлена на рассмотрение.\n\n"
            "Ожидайте одобрения от администратора."
        )
        return
    
    await state.set_state(RegistrationStates.waiting_role)
    
    # Клавиатура выбора роли
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💼 Медиабаер", callback_data="reg_role_buyer")],
        [InlineKeyboardButton(text="👨‍💼 Тимлид", callback_data="reg_role_teamlead")],
        [InlineKeyboardButton(text="📈 Бизнес-дев", callback_data="reg_role_bizdev")],
        [InlineKeyboardButton(text="💰 Финансист", callback_data="reg_role_finance")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="reg_cancel")]
    ])
    
    text = f"""
📝 <b>Регистрация в системе</b>

👋 Привет, {message.from_user.first_name}!

🎯 <b>Выберите вашу роль:</b>

• <b>Медиабаер</b> - работа с креативами и трафиком
• <b>Тимлид</b> - управление командой баеров
• <b>Бизнес-дев</b> - работа с партнерами
• <b>Финансист</b> - финансовые отчеты
"""
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("reg_role_"))
async def handle_role_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора роли"""
    role = callback.data.replace("reg_role_", "")
    
    await state.update_data(role=role)
    
    role_names = {
        'buyer': '💼 Медиабаер',
        'teamlead': '👨‍💼 Тимлид',
        'bizdev': '📈 Бизнес-дев',
        'finance': '💰 Финансист'
    }
    
    if role == 'buyer':
        await state.set_state(RegistrationStates.waiting_buyer_id)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить", callback_data="reg_cancel")]
        ])
        
        text = f"""
🏷️ <b>Укажите ваш Buyer ID</b>

Вы выбрали роль: {role_names[role]}

📝 <b>Отправьте сообщением ваш Buyer ID</b>

💡 Пример: <code>n1</code>, <code>kk1</code>, <code>az1</code>

⚠️ Это <b>НЕ</b> ваш Telegram ID, а ID баера в системе!
"""
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await state.set_state(RegistrationStates.waiting_confirmation)
        await state.update_data(buyer_id=None)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data="reg_confirm")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="reg_cancel")]
        ])
        
        text = f"""
✅ <b>Подтверждение регистрации</b>

👤 <b>Telegram ID:</b> <code>{callback.from_user.id}</code>
👤 <b>Имя:</b> {callback.from_user.first_name}
🎯 <b>Роль:</b> {role_names[role]}

📝 Подтвердите отправку заявки?
"""
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    
    await callback.answer()

@router.message(RegistrationStates.waiting_buyer_id)
async def handle_buyer_id_input(message: Message, state: FSMContext):
    """Обработка ввода Buyer ID"""
    buyer_id = message.text.strip()
    
    # Простая валидация
    if len(buyer_id) < 1 or len(buyer_id) > 10:
        await message.answer(
            "❌ <b>Некорректный Buyer ID!</b>\n\n"
            "💡 Buyer ID должен быть от 1 до 10 символов.\n"
            "Отправьте корректный ID.",
            parse_mode="HTML"
        )
        return
    
    await state.update_data(buyer_id=buyer_id)
    await state.set_state(RegistrationStates.waiting_confirmation)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="reg_confirm")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="reg_cancel")]
    ])
    
    text = f"""
✅ <b>Подтверждение регистрации</b>

👤 <b>Telegram ID:</b> <code>{message.from_user.id}</code>
👤 <b>Имя:</b> {message.from_user.first_name}
🎯 <b>Роль:</b> 💼 Медиабаер
🏷️ <b>Buyer ID:</b> <code>{buyer_id}</code>

📝 Подтвердите отправку заявки?
"""
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "reg_confirm")
async def handle_registration_confirm(callback: CallbackQuery, state: FSMContext):
    """Подтверждение регистрации"""
    user_data = await state.get_data()
    user_id = callback.from_user.id
    role = user_data.get('role')
    buyer_id = user_data.get('buyer_id')
    
    # Сохраняем заявку
    pending = load_pending_users()
    pending[user_id] = {
        'role': role,
        'buyer_id': buyer_id,
        'username': callback.from_user.username,
        'first_name': callback.from_user.first_name,
        'last_name': callback.from_user.last_name,
        'created_at': datetime.now().isoformat()
    }
    
    if save_pending_users(pending):
        await callback.message.edit_text(
            "✅ <b>Заявка отправлена!</b>\n\n"
            "📝 Ваша заявка отправлена администраторам.\n\n"
            "⏳ Ожидайте одобрения. Мы уведомим вас о результате.",
            parse_mode="HTML"
        )
        
        # Уведомляем админов
        await notify_admins_about_new_request(callback.from_user, role, buyer_id)
        
    else:
        await callback.message.edit_text(
            "❌ <b>Ошибка!</b>\n\n"
            "Не удалось отправить заявку. Попробуйте позже.",
            parse_mode="HTML"
        )
    
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "reg_cancel")
async def handle_registration_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена регистрации"""
    await state.clear()
    await callback.message.edit_text(
        "❌ <b>Регистрация отменена</b>\n\n"
        "💡 Для повторной регистрации используйте /register",
        parse_mode="HTML"
    )
    await callback.answer()

async def notify_admins_about_new_request(user, role: str, buyer_id: str):
    """Уведомление админов о новой заявке"""
    bot = Bot(token=settings.telegram_bot_token)
    
    admins = get_admin_list()
    
    role_names = {
        'buyer': '💼 Медиабаер',
        'teamlead': '👨‍💼 Тимлид',
        'bizdev': '📈 Бизнес-дев',
        'finance': '💰 Финансист'
    }
    
    buyer_text = f"\n🏷️ <b>Buyer ID:</b> <code>{buyer_id}</code>" if buyer_id else ""
    
    text = f"""
🔔 <b>Новая заявка на регистрацию!</b>

👤 <b>Telegram ID:</b> <code>{user.id}</code>
👤 <b>Имя:</b> {user.first_name or 'Не указано'}
🎯 <b>Роль:</b> {role_names.get(role, role)}{buyer_text}

📝 <b>Для рассмотрения заявок используйте:</b>
/pending - Посмотреть все заявки
"""
    
    # Отправляем всем админам
    for admin_id in admins:
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

# ===== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ =====

@router.message(Command("users"))
async def cmd_users(message: Message):
    """Список пользователей"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("❌ Недостаточно прав для выполнения команды.")
        return
    
    users = load_users()
    
    if not users:
        await message.answer("📝 Список пользователей пуст.")
        return
    
    text = "👥 <b>Список пользователей:</b>\n\n"
    
    role_names = {
        'owner': '👑 Владелец',
        'head': '🎯 Хед медиабаинга', 
        'teamlead': '👨‍💼 Тимлид',
        'buyer': '💼 Медиабаер',
        'bizdev': '📈 Бизнес-дев',
        'finance': '💰 Финансист'
    }
    
    for tg_id, user_info in users.items():
        role = user_info.get('role', 'unknown')
        buyer_id = user_info.get('buyer_id', '')
        
        role_display = role_names.get(role, f"❓ {role}")
        buyer_display = f" | Buyer: {buyer_id}" if buyer_id else ""
        
        text += f"• <code>{tg_id}</code> - {role_display}{buyer_display}\n"
    
    text += f"\n📊 Всего пользователей: {len(users)}"
    
    await message.answer(text, parse_mode="HTML")

@router.message(Command("add_user"))
async def cmd_add_user(message: Message):
    """Добавить пользователя
    
    Формат: /add_user <telegram_id> <role> [buyer_id]
    Роли: owner, head, teamlead, buyer, bizdev, finance
    
    Пример: /add_user 123456789 buyer n1
    """
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("❌ Недостаточно прав для выполнения команды.")
        return
    
    # Парсим аргументы
    args = message.text.split()[1:]  # Убираем /add_user
    
    if len(args) < 2:
        await message.answer(
            "❌ <b>Неправильный формат команды!</b>\n\n"
            "📖 <b>Использование:</b>\n"
            "<code>/add_user &lt;telegram_id&gt; &lt;role&gt; [buyer_id]</code>\n\n"
            "🔧 <b>Доступные роли:</b>\n"
            "• <code>owner</code> - Владелец (полные права)\n"
            "• <code>head</code> - Хед медиабаинга\n" 
            "• <code>teamlead</code> - Тимлид\n"
            "• <code>buyer</code> - Медиабаер\n"
            "• <code>bizdev</code> - Бизнес-дев\n"
            "• <code>finance</code> - Финансист\n\n"
            "💡 <b>Пример:</b>\n"
            "<code>/add_user 123456789 buyer n1</code>",
            parse_mode="HTML"
        )
        return
    
    try:
        tg_id = int(args[0])
    except ValueError:
        await message.answer("❌ Telegram ID должен быть числом!")
        return
    
    role = args[1].lower()
    valid_roles = ['owner', 'head', 'teamlead', 'buyer', 'bizdev', 'finance']
    
    if role not in valid_roles:
        await message.answer(
            f"❌ Недопустимая роль: {role}\n\n"
            f"✅ Доступные роли: {', '.join(valid_roles)}"
        )
        return
    
    buyer_id = args[2] if len(args) > 2 else None
    
    # Загружаем и обновляем список пользователей
    users = load_users()
    
    if tg_id in users:
        await message.answer(f"⚠️ Пользователь {tg_id} уже существует!\nИспользуйте /edit_user для изменения.")
        return
    
    users[tg_id] = {
        'role': role,
        'buyer_id': buyer_id
    }
    
    if save_users(users):
        role_names = {
            'owner': '👑 Владелец',
            'head': '🎯 Хед медиабаинга',
            'teamlead': '👨‍💼 Тимлид', 
            'buyer': '💼 Медиабаер',
            'bizdev': '📈 Бизнес-дев',
            'finance': '💰 Финансист'
        }
        
        role_display = role_names.get(role, role)
        buyer_text = f"\n🏷 Buyer ID: {buyer_id}" if buyer_id else ""
        
        await message.answer(
            f"✅ <b>Пользователь добавлен!</b>\n\n"
            f"🆔 Telegram ID: <code>{tg_id}</code>\n"
            f"👤 Роль: {role_display}{buyer_text}\n\n"
            f"🔄 Перезагрузите бота для применения изменений.",
            parse_mode="HTML"
        )
        
        logger.info(f"User {user_id} added new user {tg_id} with role {role}")
    else:
        await message.answer("❌ Ошибка при сохранении пользователя!")

@router.message(Command("remove_user"))
async def cmd_remove_user(message: Message):
    """Удалить пользователя
    
    Формат: /remove_user <telegram_id>
    """
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("❌ Недостаточно прав для выполнения команды.")
        return
    
    args = message.text.split()[1:]
    
    if len(args) != 1:
        await message.answer(
            "❌ <b>Неправильный формат команды!</b>\n\n"
            "📖 <b>Использование:</b>\n"
            "<code>/remove_user &lt;telegram_id&gt;</code>\n\n"
            "💡 <b>Пример:</b>\n"
            "<code>/remove_user 123456789</code>",
            parse_mode="HTML"
        )
        return
    
    try:
        tg_id = int(args[0])
    except ValueError:
        await message.answer("❌ Telegram ID должен быть числом!")
        return
    
    users = load_users()
    
    if tg_id not in users:
        await message.answer(f"❌ Пользователь {tg_id} не найден!")
        return
    
    if tg_id == user_id:
        await message.answer("❌ Нельзя удалить самого себя!")
        return
    
    user_info = users[tg_id]
    del users[tg_id]
    
    if save_users(users):
        await message.answer(
            f"✅ <b>Пользователь удален!</b>\n\n"
            f"🆔 Telegram ID: <code>{tg_id}</code>\n"
            f"👤 Роль была: {user_info.get('role', 'unknown')}\n\n"
            f"🔄 Перезагрузите бота для применения изменений.",
            parse_mode="HTML"
        )
        
        logger.info(f"User {user_id} removed user {tg_id}")
    else:
        await message.answer("❌ Ошибка при сохранении изменений!")

@router.message(Command("edit_user"))
async def cmd_edit_user(message: Message):
    """Изменить роль пользователя
    
    Формат: /edit_user <telegram_id> <role> [buyer_id]
    """
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("❌ Недостаточно прав для выполнения команды.")
        return
    
    args = message.text.split()[1:]
    
    if len(args) < 2:
        await message.answer(
            "❌ <b>Неправильный формат команды!</b>\n\n"
            "📖 <b>Использование:</b>\n"
            "<code>/edit_user &lt;telegram_id&gt; &lt;role&gt; [buyer_id]</code>\n\n"
            "💡 <b>Пример:</b>\n"
            "<code>/edit_user 123456789 teamlead</code>",
            parse_mode="HTML"
        )
        return
    
    try:
        tg_id = int(args[0])
    except ValueError:
        await message.answer("❌ Telegram ID должен быть числом!")
        return
    
    role = args[1].lower()
    valid_roles = ['owner', 'head', 'teamlead', 'buyer', 'bizdev', 'finance']
    
    if role not in valid_roles:
        await message.answer(f"❌ Недопустимая роль: {role}\n\n✅ Доступные роли: {', '.join(valid_roles)}")
        return
    
    buyer_id = args[2] if len(args) > 2 else None
    
    users = load_users()
    
    if tg_id not in users:
        await message.answer(f"❌ Пользователь {tg_id} не найден!\nИспользуйте /add_user для добавления.")
        return
    
    old_role = users[tg_id].get('role', 'unknown')
    old_buyer = users[tg_id].get('buyer_id', '')
    
    users[tg_id]['role'] = role
    if buyer_id is not None:
        users[tg_id]['buyer_id'] = buyer_id
    
    if save_users(users):
        await message.answer(
            f"✅ <b>Пользователь обновлен!</b>\n\n"
            f"🆔 Telegram ID: <code>{tg_id}</code>\n"
            f"👤 Роль: {old_role} → {role}\n"
            f"🏷 Buyer ID: {old_buyer or 'нет'} → {buyer_id or 'нет'}\n\n"
            f"🔄 Перезагрузите бота для применения изменений.",
            parse_mode="HTML"
        )
        
        logger.info(f"User {user_id} edited user {tg_id}: {old_role} -> {role}")
    else:
        await message.answer("❌ Ошибка при сохранении изменений!")

# ===== ОБНОВЛЕННОЕ МЕНЮ АДМИНА =====

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Справка по админ-командам"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("❌ Недостаточно прав для выполнения команды.")
        return
    
    help_text = """
🔧 <b>Новая система управления пользователями:</b>

🆕 <b>Команды с кнопками (рекомендуем):</b>
🔧 <b>/manage_users</b> - Кнопочное управление
📝 <b>/pending</b> - Посмотреть заявки на регистрацию

ℹ️ <b>Классические команды:</b>
👥 <b>/users</b> - Список всех пользователей
➕ <b>/add_user &lt;id&gt; &lt;role&gt; [buyer_id]</b> - Добавить
✏️ <b>/edit_user &lt;id&gt; &lt;role&gt; [buyer_id]</b> - Изменить
❌ <b>/remove_user &lt;id&gt;</b> - Удалить

🔄 <b>Пользователям:</b>
📝 <b>/register</b> - Подать заявку на регистрацию

🔧 <b>Иерархия прав:</b>
👑 <b>Owner</b> - может всё (супер админ)
🎯 <b>Head/Teamlead</b> - могут апрувить/удалять только баеров
💼 <b>Buyer</b> - должен указать свой Buyer ID

💡 <b>Пример работы:</b>
1. Пользователь: /register
2. Админ: /pending (или /manage_users)
3. Нажимает кнопку "✅ Одобрить"
"""
    
    await message.answer(help_text, parse_mode="HTML")

# ===== УПРАВЛЕНИЕ ЗАЯВКАМИ =====

@router.message(Command("pending"))
async def cmd_pending_users(message: Message):
    """Показать все заявки на регистрацию"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("❌ Недостаточно прав для выполнения команды.")
        return
    
    pending = load_pending_users()
    
    if not pending:
        await message.answer("✅ <b>Новых заявок нет!</b>", parse_mode="HTML")
        return
    
    role_names = {
        'buyer': '💼 Медиабаер',
        'teamlead': '👨‍💼 Тимлид',
        'bizdev': '📈 Бизнес-дев',
        'finance': '💰 Финансист'
    }
    
    for tg_id, user_info in pending.items():
        role = user_info.get('role', 'unknown')
        buyer_id = user_info.get('buyer_id')
        username = user_info.get('username')
        first_name = user_info.get('first_name', 'Не указано')
        created_at = user_info.get('created_at', '')
        
        # Проверяем права на апрув
        can_approve = can_approve_user(user_id, role)
        
        buyer_text = f"\n🏷️ <b>Buyer ID:</b> <code>{buyer_id}</code>" if buyer_id else ""
        username_text = f"\n📄 <b>Username:</b> @{username}" if username else ""
        
        text = f"""
📝 <b>Заявка на регистрацию</b>

👤 <b>Telegram ID:</b> <code>{tg_id}</code>
👤 <b>Имя:</b> {first_name}{username_text}
🎯 <b>Роль:</b> {role_names.get(role, role)}{buyer_text}

🗺️ <b>Подано:</b> {created_at[:16].replace('T', ' ')}
"""
        
        if can_approve:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{tg_id}"),
                    InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{tg_id}")
                ]
            ])
        else:
            text += "\n⚠️ <i>У вас нет прав на апрув этой роли</i>"
            keyboard = None
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("approve_"))
async def handle_approve_user(callback: CallbackQuery):
    """Одобрение пользователя"""
    admin_id = callback.from_user.id
    target_id = int(callback.data.replace("approve_", ""))
    
    if not is_admin(admin_id):
        await callback.answer("❌ Недостаточно прав!", show_alert=True)
        return
    
    pending = load_pending_users()
    
    if target_id not in pending:
        await callback.answer("❌ Заявка не найдена!", show_alert=True)
        return
    
    user_info = pending[target_id]
    role = user_info.get('role')
    
    # Проверяем права
    if not can_approve_user(admin_id, role):
        await callback.answer("❌ У вас нет прав на апрув этой роли!", show_alert=True)
        return
    
    # Сохраняем пользователя в базу данных
    user_data = {
        'role': role,
        'buyer_id': user_info.get('buyer_id'),
        'username': user_info.get('username', ''),
        'first_name': user_info.get('first_name', ''),
    }
    
    # Сохраняем в PostgreSQL
    db_save_success = await save_user_to_database(target_id, user_data, admin_id)
    
    if db_save_success:
        # Дополнительно сохраняем в JSON файл для обратной совместимости
        users = load_users()
        users[target_id] = {
            'role': role,
            'buyer_id': user_info.get('buyer_id'),
            'approved_by': admin_id,
            'approved_at': datetime.now().isoformat()
        }
        save_users(users)  # Не блокируем на ошибке файла
        
        # Удаляем из ожидания
        del pending[target_id]
        save_pending_users(pending)
        
        # Синхронизируем settings с базой данных
        await sync_settings_with_database()
        
        role_names = {
            'buyer': '💼 Медиабаер',
            'teamlead': '👨‍💼 Тимлид',
            'bizdev': '📈 Бизнес-дев',
            'finance': '💰 Финансист'
        }
        
        await callback.message.edit_text(
            f"✅ <b>Пользователь одобрен!</b>\n\n"
            f"👤 <b>ID:</b> <code>{target_id}</code>\n"
            f"🎯 <b>Роль:</b> {role_names.get(role, role)}\n"
            f"✅ <b>Одобрил:</b> {callback.from_user.first_name}",
            parse_mode="HTML"
        )
        
        # Уведомляем пользователя
        await notify_user_approved(target_id, role)
        
        logger.info(f"Admin {admin_id} approved user {target_id} with role {role} - saved to PostgreSQL")
    else:
        await callback.answer("❌ Ошибка при сохранении в базу данных!", show_alert=True)
    
    await callback.answer()

@router.callback_query(F.data.startswith("reject_"))
async def handle_reject_user(callback: CallbackQuery):
    """Отклонение пользователя"""
    admin_id = callback.from_user.id
    target_id = int(callback.data.replace("reject_", ""))
    
    if not is_admin(admin_id):
        await callback.answer("❌ Недостаточно прав!", show_alert=True)
        return
    
    pending = load_pending_users()
    
    if target_id not in pending:
        await callback.answer("❌ Заявка не найдена!", show_alert=True)
        return
    
    user_info = pending[target_id]
    role = user_info.get('role')
    
    # Проверяем права
    if not can_approve_user(admin_id, role):
        await callback.answer("❌ У вас нет прав на отклонение этой роли!", show_alert=True)
        return
    
    # Удаляем заявку
    del pending[target_id]
    
    if save_pending_users(pending):
        await callback.message.edit_text(
            f"❌ <b>Заявка отклонена!</b>\n\n"
            f"👤 <b>ID:</b> <code>{target_id}</code>\n"
            f"❌ <b>Отклонил:</b> {callback.from_user.first_name}",
            parse_mode="HTML"
        )
        
        # Уведомляем пользователя
        await notify_user_rejected(target_id)
        
        logger.info(f"Admin {admin_id} rejected user {target_id}")
    else:
        await callback.answer("❌ Ошибка при сохранении!", show_alert=True)
    
    await callback.answer()

async def notify_user_approved(user_id: int, role: str):
    """Уведомление об одобрении"""
    bot = Bot(token=settings.telegram_bot_token)
    
    role_names = {
        'buyer': '💼 Медиабаер',
        'teamlead': '👨‍💼 Тимлид',
        'bizdev': '📈 Бизнес-дев',
        'finance': '💰 Финансист'
    }
    
    text = f"""
✅ <b>Ваша заявка одобрена!</b>

🎯 <b>Роль:</b> {role_names.get(role, role)}

🎉 Добро пожаловать в команду!

📝 Используйте /start для начала работы.
"""
    
    try:
        await bot.send_message(user_id, text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to notify user {user_id} about approval: {e}")

async def notify_user_rejected(user_id: int):
    """Уведомление об отклонении"""
    bot = Bot(token=settings.telegram_bot_token)
    
    text = f"""
❌ <b>Ваша заявка отклонена</b>

📝 Если считаете это ошибкой, обратитесь к администратору.

Для повторной подачи заявки используйте /register
"""
    
    try:
        await bot.send_message(user_id, text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to notify user {user_id} about rejection: {e}")

@router.message(Command("reload_users"))
async def cmd_reload_users(message: Message):
    """Перезагрузить список пользователей"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("❌ Недостаточно прав для выполнения команды.")
        return
    
    try:
        # Обновляем конфиг
        users = load_users()
        settings.allowed_users = users
        
        await message.answer(
            f"✅ <b>Список пользователей перезагружен!</b>\n\n"
            f"👥 Загружено пользователей: {len(users)}\n"
            f"📁 Источник: {USERS_FILE if os.path.exists(USERS_FILE) else 'конфиг'}"
        )
        
        logger.info(f"User {user_id} reloaded users list")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при перезагрузке: {e}")
        logger.error(f"Error reloading users: {e}")

# ===== КНОПОЧНОЕ УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ =====

@router.message(Command("manage_users"))
async def cmd_manage_users(message: Message):
    """Кнопочное управление пользователями"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("❌ Недостаточно прав для выполнения команды.")
        return
    
    # Получаем статистику
    users = load_users()
    pending = load_pending_users()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"📝 Заявки ({len(pending)})", callback_data="btn_pending"),
            InlineKeyboardButton(text=f"👥 Пользователи ({len(users)})", callback_data="btn_users_list")
        ],
        [
            InlineKeyboardButton(text="➕ Добавить пользователя", callback_data="btn_add_user"),
        ],
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data="btn_refresh_manage")
        ]
    ])
    
    text = f"""
🔧 <b>Управление пользователями</b>

📊 <b>Текущая статистика:</b>
• Активные пользователи: {len(users)}
• Ожидают одобрения: {len(pending)}

Выберите действие:
"""
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "btn_pending")
async def handle_btn_pending(callback: CallbackQuery):
    """Показать заявки"""
    await callback.answer()
    # Перенаправляем на команду pending
    fake_message = type('obj', (object,), {
        'from_user': callback.from_user,
        'answer': callback.message.answer
    })
    await cmd_pending_users(fake_message)

@router.callback_query(F.data == "btn_users_list")
async def handle_btn_users_list(callback: CallbackQuery):
    """Показать список пользователей"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Недостаточно прав!", show_alert=True)
        return
    
    users = load_users()
    
    if not users:
        await callback.message.edit_text("📝 Список пользователей пуст.")
        return
    
    role_names = {
        'owner': '👑 Владелец',
        'head': '🎯 Хед медиабаинга',
        'teamlead': '👨‍💼 Тимлид',
        'buyer': '💼 Медиабаер',
        'bizdev': '📈 Бизнес-дев',
        'finance': '💰 Финансист'
    }
    
    text = "👥 <b>Список пользователей:</b>\n\n"
    
    # Сортируем по ролям
    sorted_users = sorted(users.items(), key=lambda x: ['owner', 'head', 'teamlead', 'buyer', 'bizdev', 'finance'].index(x[1].get('role', 'buyer')))
    
    keyboards = []
    
    for tg_id, user_info in sorted_users[:10]:  # Показываем первые 10
        role = user_info.get('role', 'unknown')
        buyer_id = user_info.get('buyer_id', '')
        
        role_display = role_names.get(role, f"❓ {role}")
        buyer_display = f" | {buyer_id}" if buyer_id else ""
        
        text += f"• <code>{tg_id}</code> - {role_display}{buyer_display}\n"
        
        # Проверяем права на удаление
        can_delete = can_delete_user(user_id, role, tg_id)
        
        if can_delete:
            keyboards.append([
                InlineKeyboardButton(
                    text=f"❌ {tg_id}{'|' + buyer_id if buyer_id else ''}",
                    callback_data=f"delete_user_{tg_id}"
                )
            ])
    
    if len(users) > 10:
        text += f"\n... и еще {len(users) - 10} пользователей"
    
    keyboards.append([
        InlineKeyboardButton(text="← Назад", callback_data="btn_refresh_manage")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboards)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("delete_user_"))
async def handle_delete_user_confirm(callback: CallbackQuery):
    """Подтверждение удаления"""
    admin_id = callback.from_user.id
    target_id = int(callback.data.replace("delete_user_", ""))
    
    users = load_users()
    
    if target_id not in users:
        await callback.answer("❌ Пользователь не найден!", show_alert=True)
        return
    
    user_info = users[target_id]
    role = user_info.get('role')
    
    # Проверяем права
    if not can_delete_user(admin_id, role, target_id):
        await callback.answer("❌ У вас нет прав на удаление этого пользователя!", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_delete_{target_id}"),
            InlineKeyboardButton(text="❌ Отменить", callback_data="btn_users_list")
        ]
    ])
    
    role_names = {
        'owner': '👑 Владелец',
        'head': '🎯 Хед',
        'teamlead': '👨‍💼 Тимлид',
        'buyer': '💼 Медиабаер',
        'bizdev': '📈 Бизнес-дев',
        'finance': '💰 Финансист'
    }
    
    buyer_text = f"\n🏷️ <b>Buyer ID:</b> {user_info.get('buyer_id')}" if user_info.get('buyer_id') else ""
    
    text = f"""
⚠️ <b>Подтверждение удаления</b>

👤 <b>ID:</b> <code>{target_id}</code>
🎯 <b>Роль:</b> {role_names.get(role, role)}{buyer_text}

❌ <b>Вы уверены, что хотите удалить этого пользователя?</b>
"""
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_delete_"))
async def handle_confirm_delete_user(callback: CallbackQuery):
    """Окончательное удаление"""
    admin_id = callback.from_user.id
    target_id = int(callback.data.replace("confirm_delete_", ""))
    
    users = load_users()
    
    if target_id not in users:
        await callback.answer("❌ Пользователь не найден!", show_alert=True)
        return
    
    user_info = users[target_id]
    role = user_info.get('role')
    
    if not can_delete_user(admin_id, role, target_id):
        await callback.answer("❌ Недостаточно прав!", show_alert=True)
        return
    
    # Удаляем
    del users[target_id]
    
    if save_users(users):
        settings.allowed_users = users
        
        await callback.message.edit_text(
            f"✅ <b>Пользователь удален!</b>\n\n"
            f"👤 <b>ID:</b> <code>{target_id}</code>\n"
            f"❌ <b>Удалил:</b> {callback.from_user.first_name}",
            parse_mode="HTML"
        )
        
        # Уведомляем пользователя
        await notify_user_deleted(target_id)
        
        logger.info(f"Admin {admin_id} deleted user {target_id}")
    else:
        await callback.answer("❌ Ошибка при удалении!", show_alert=True)
    
    await callback.answer()

@router.callback_query(F.data == "btn_refresh_manage")
async def handle_btn_refresh_manage(callback: CallbackQuery):
    """Обновление главного меню"""
    await callback.answer()
    fake_message = type('obj', (object,), {
        'from_user': callback.from_user,
        'answer': callback.message.edit_text
    })
    await cmd_manage_users(fake_message)

def can_delete_user(admin_id: int, target_role: str, target_id: int) -> bool:
    """Проверка прав на удаление пользователя"""
    users = load_users()
    admin_info = users.get(admin_id, {})
    admin_role = admin_info.get('role', '')
    
    # Нельзя удалить самого себя
    if admin_id == target_id:
        return False
    
    # Owner может удалять кого угодно (кроме себя)
    if admin_role == 'owner':
        return True
    
    # Head и teamlead могут удалять только buyers
    if admin_role in ['head', 'teamlead'] and target_role == 'buyer':
        return True
    
    return False

async def notify_user_deleted(user_id: int):
    """Уведомление об удалении"""
    bot = Bot(token=settings.telegram_bot_token)
    
    text = """
❌ <b>Ваш доступ заблокирован</b>

Вас исключили из системы.

📞 Для восстановления доступа обратитесь к администратору.
"""
    
    try:
        await bot.send_message(user_id, text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to notify user {user_id} about deletion: {e}")