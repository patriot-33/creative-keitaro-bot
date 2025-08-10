import asyncio
import logging
import sys
from pathlib import Path
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.config import settings
from db.database import engine
from db.models import Base
from bot.handlers import reports, admin, upload, google_auth

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token=settings.telegram_bot_token)
dp = Dispatcher(storage=MemoryStorage())

# Register routers
dp.include_router(reports.router)
dp.include_router(admin.router)
dp.include_router(upload.router)
dp.include_router(google_auth.router)


@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Handle /start command"""
    user = message.from_user
    logger.info(f"Received /start from user {user.id} ({user.username})")
    
    # Check if user is in whitelist
    allowed_users = settings.allowed_users
    user_info = allowed_users.get(user.id) or allowed_users.get(str(user.id))
    
    if not user_info:
        logger.info(f"Unregistered user {user.id} ({user.username}) accessed /start")
        
        # Проверяем, есть ли уже заявка на регистрацию
        from bot.handlers.admin import load_pending_users
        pending = load_pending_users()
        
        if user.id in pending:
            await message.answer(
                "⏳ **Ваша заявка на рассмотрении**\n\n"
                f"🆔 Ваш ID: `{user.id}`\n"
                "📝 Заявка отправлена администраторам\n\n"
                "⏰ Ожидайте одобрения. Мы уведомим вас о результате.",
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                f"👋 **Добро пожаловать, {user.first_name}!**\n\n"
                "🔐 Для доступа к боту необходимо зарегистрироваться\n\n"
                f"🆔 **Ваш Telegram ID:** `{user.id}`\n\n"
                "📝 **Для регистрации используйте:**\n"
                "/register - Подать заявку на регистрацию\n\n"
                "✨ После одобрения админом вы получите полный доступ к боту!",
                parse_mode="Markdown"
            )
        return
    
    role = user_info.get('role', 'unknown')
    buyer_id = user_info.get('buyer_id', 'не указан')
    
    role_names = {
        'owner': 'Владелец',
        'head': 'Хед медиабаинга',
        'teamlead': 'Тимлид',
        'buyer': 'Медиабаер',
        'bizdev': 'Бизнес-дев',
        'finance': 'Финансист'
    }
    
    # Админ-команды для владельца и хеда
    admin_commands = ""
    if role in ['owner', 'head', 'teamlead']:
        admin_commands = """
🔧 <b>Админ-команды:</b>
/manage_users - 🎛️ Управление пользователями (кнопки)
/pending - 📋 Заявки на регистрацию
/admin - 📖 Полная справка по командам
"""
    
    # Этот блок кода теперь выполняется только для авторизованных пользователей
    
    welcome_text = f"""
👋 Привет, {user.first_name}!

Я - Team Creative Manager Bot.
Помогаю управлять креативами для медиабаинга.

🆔 Ваш ID: {user.id}
👤 Роль: {role_names.get(role, role) if user_info else 'Не авторизован'}
🏷 Buyer ID: {buyer_id}

📊 <b>Основные команды:</b>
/reports - 📊 Система отчетов (новая!)
/upload - Загрузить креатив
/google_auth - 🔐 Авторизация Google Drive
/stats_creo - Статистика креативов
/stats_buyer - Статистика по баерам
/stats_geo_offer - Статистика GEO/офферов
/my_creos - Мои креативы
/export - Экспорт в Excel
/help - Помощь{admin_commands}

Для начала работы используйте /reports
"""
    
    await message.answer(welcome_text, parse_mode="HTML")
    logger.info(f"User {user.id} ({user.username}) started the bot with role {role}")


@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command"""
    help_text = """
📋 Справка по командам:

/upload - Загрузка нового креатива
  • Поддерживаются: JPG, PNG, MP4, MOV
  • Максимальный размер: 50 МБ
  • Автоматическая генерация ID

/stats_creo - Статистика по креативам
  • Фильтры: период, GEO, оффер, баер
  • Показатели: клики, регистрации, депозиты

/stats_buyer - Статистика по баерам
  • Агрегированные данные по баерам
  • Топ креативы каждого баера

/stats_geo_offer - Статистика по GEO и офферам
  • Срезы по странам
  • Эффективность офферов

/my_creos - Ваши последние креативы
  • Последние 20 загруженных креативов
  • Сортировка по эффективности

/export - Экспорт текущего отчета
  • Форматы: CSV, XLSX
  • Файл отправляется в чат

По всем вопросам: @your_support
"""
    
    await message.answer(help_text)


async def load_users_from_database():
    """Загрузка пользователей из базы данных при запуске"""
    try:
        from db.database import get_db_session
        from db.models.user import User
        from sqlalchemy import select
        from core.enums import UserRole
        
        async with get_db_session() as session:
            # Получаем всех пользователей из БД
            result = await session.execute(select(User))
            db_users = result.scalars().all()
            
            # Конвертируем в формат settings
            users = {}
            for user in db_users:
                users[str(user.tg_user_id)] = {
                    'role': user.role.value,
                    'buyer_id': user.buyer_id or '',
                    'username': user.tg_username or '',
                    'first_name': user.full_name or '',
                    'is_approved': user.is_active
                }
            
            # Добавляем пользователей из ENV переменной ALLOWED_USERS (приоритет)
            env_users = settings.allowed_users.copy() if hasattr(settings, 'allowed_users') and settings.allowed_users else {}
            
            # Объединяем БД пользователей с ENV пользователями (ENV имеет приоритет)
            for env_user_id, env_user_data in env_users.items():
                users[str(env_user_id)] = env_user_data
            
            settings.allowed_users = users
            logger.info(f"Loaded {len(users)} users from database + ENV (ENV users have priority)")
            logger.info(f"Loaded users: {list(users.keys())}")
            
            # Если нет пользователей вообще, загружаем из файла как fallback
            if not users:
                from bot.handlers.admin import load_users
                file_users = load_users()
                if file_users:
                    # Синхронизируем файловых пользователей в БД
                    await sync_file_users_to_database(session, file_users)
                    settings.allowed_users = file_users
                    logger.info(f"Migrated {len(file_users)} users from file to database")
                
    except Exception as e:
        logger.warning(f"Failed to load users from database: {e}")
        # Fallback к файлу
        try:
            from bot.handlers.admin import load_users
            users = load_users()
            settings.allowed_users = users
            logger.info(f"Loaded {len(users)} users from file (fallback)")
        except Exception as file_error:
            logger.error(f"Failed to load users from file fallback: {file_error}")

async def sync_file_users_to_database(session, file_users):
    """Синхронизация пользователей из файла в базу данных"""
    from db.models.user import User
    from sqlalchemy import select
    
    for tg_id, user_data in file_users.items():
        # Проверяем, существует ли пользователь
        result = await session.execute(select(User).where(User.tg_user_id == int(tg_id)))
        existing_user = result.scalar_one_or_none()
        
        if not existing_user:
            # Создаем нового пользователя
            new_user = User(
                tg_user_id=int(tg_id),
                tg_username=user_data.get('username', ''),
                full_name=user_data.get('first_name', ''),
                role=UserRole(user_data.get('role', 'buyer')),
                buyer_id=user_data.get('buyer_id') if user_data.get('buyer_id') else None,
                is_active=user_data.get('is_approved', True)
            )
            session.add(new_user)
    
    await session.commit()

async def on_startup():
    """Startup tasks"""
    logger.info("Starting bot...")
    
    # Load users from database
    await load_users_from_database()
    
    # Create database tables
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized successfully!")
    except Exception as e:
        logger.warning(f"Database initialization failed: {e}")
        logger.info("Bot will continue without database features")
    
    logger.info("Bot started successfully!")


async def on_shutdown():
    """Shutdown tasks"""
    logger.info("Shutting down bot...")
    await bot.session.close()
    await engine.dispose()


async def main():
    """Main function"""
    # Register startup and shutdown hooks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Start polling
    try:
        logger.info("Starting polling...")
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main())