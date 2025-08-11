import asyncio
import logging
import sys
import signal
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

# Configure logging - EMERGENCY: Set to ERROR level for reports debugging
logging.basicConfig(
    level=logging.ERROR,
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


# EMERGENCY DEBUG: Log all incoming messages
@dp.message()
async def log_all_messages(message: Message):
    """Log all incoming messages for debugging"""
    logger.error(f"🚨 EMERGENCY DEBUG: Message received - command: {message.text}, user: {message.from_user.id}")

@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Handle /start command"""
    user = message.from_user
    logger.info(f"Received /start from user {user.id} ({user.username})")
    
    # Check if user is in whitelist
    allowed_users = settings.allowed_users
    user_info = allowed_users.get(user.id) or allowed_users.get(str(user.id))
    
    # Debug logging
    logger.info(f"User {user.id} lookup: user_info={user_info}")
    logger.info(f"Available users: {list(allowed_users.keys())}")
    logger.info(f"User types: {[(k, type(k)) for k in allowed_users.keys()]}")
    
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
            
            # Синхронизируем ENV пользователей в БД (чтобы избежать FK ошибок)
            try:
                await sync_file_users_to_database(session, env_users)
                logger.info(f"Synced {len(env_users)} ENV users to database")
            except Exception as sync_error:
                logger.error(f"Failed to sync ENV users to database: {sync_error}")
            
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
    from core.enums import UserRole
    
    logger.info(f"=== SYNC ENV USERS DEBUG ===")
    logger.info(f"Syncing {len(file_users)} users: {list(file_users.keys())}")
    
    for tg_id, user_data in file_users.items():
        logger.info(f"Processing user {tg_id}: {user_data}")
        
        # Проверяем, существует ли пользователь
        result = await session.execute(select(User).where(User.tg_user_id == int(tg_id)))
        existing_user = result.scalar_one_or_none()
        
        if not existing_user:
            logger.info(f"Creating new user {tg_id} in database")
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
        else:
            logger.info(f"User {tg_id} already exists in database with ID {existing_user.id}")
    
    await session.commit()
    logger.info("=== SYNC COMPLETED ===")

async def force_bot_takeover():
    """Aggressively claim bot control to resolve TelegramConflictError"""
    import os
    import aiohttp
    
    logger.info("💪 EMERGENCY: Attempting aggressive bot takeover...")
    
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error('⚠️  No TELEGRAM_BOT_TOKEN found')
        return False
    
    base_url = f'https://api.telegram.org/bot{token}'
    
    try:
        connector = aiohttp.TCPConnector(enable_cleanup_closed=True)
        async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=20)) as session:
            
            logger.info('🔥 Step 1: Force delete webhook with drop_pending_updates')
            async with session.post(f'{base_url}/deleteWebhook', json={'drop_pending_updates': True}) as resp:
                result = await resp.json()
                logger.info(f'  Webhook delete result: {result}')
                
            await asyncio.sleep(3)
            
            logger.info('🔥 Step 2: Aggressive getUpdates with high offset to skip all')
            async with session.post(f'{base_url}/getUpdates', json={'offset': 999999999, 'limit': 1, 'timeout': 0}) as resp:
                result = await resp.json()
                logger.info(f'  High offset getUpdates result: {result}')
                
            await asyncio.sleep(2)
            
            logger.info('🔥 Step 3: Multiple rapid getUpdates to exhaust the queue')
            for i in range(10):
                logger.info(f'    Rapid getUpdates #{i+1}...')
                async with session.post(f'{base_url}/getUpdates', json={'offset': -1, 'limit': 100, 'timeout': 0}) as resp:
                    result = await resp.json()
                    updates_count = len(result.get('result', []))
                    logger.info(f'      Got {updates_count} updates')
                    if updates_count == 0:
                        break
                await asyncio.sleep(0.1)
            
            logger.info('🔥 Step 4: Set webhook to dummy URL to block other instances')
            dummy_url = 'https://httpbin.org/status/200'  # Safe dummy webhook
            async with session.post(f'{base_url}/setWebhook', json={'url': dummy_url, 'drop_pending_updates': True}) as resp:
                result = await resp.json()
                logger.info(f'  Dummy webhook set result: {result}')
            
            logger.info('🔥 Step 4.5: Multiple getUpdates calls to force other instances to fail')
            for attempt in range(20):  # 20 attempts to exhaust other instances
                try:
                    async with session.post(f'{base_url}/getUpdates', json={'offset': -1, 'limit': 1, 'timeout': 1}) as resp:
                        result = await resp.json()
                        if result.get('ok'):
                            logger.info(f'  Force getUpdates attempt {attempt+1}/20: success')
                        else:
                            logger.info(f'  Force getUpdates attempt {attempt+1}/20: {result}')
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.info(f'  Force getUpdates attempt {attempt+1}/20 failed: {e}')
                    await asyncio.sleep(0.5)
            
            logger.info('🔥 Waiting 30 seconds for other instances to fail completely...')
            await asyncio.sleep(30)  # Longer wait for other instances to fail
            
            logger.info('🔥 Step 5: Remove dummy webhook and prepare for polling')
            async with session.post(f'{base_url}/deleteWebhook', json={'drop_pending_updates': True}) as resp:
                result = await resp.json()
                logger.info(f'  Dummy webhook removed result: {result}')
            
            logger.info('✅ Bot takeover completed successfully')
            return True
            
    except Exception as e:
        logger.error(f'❌ Bot takeover failed: {e}')
        return False

async def on_startup():
    """Startup tasks"""
    logger.info("Starting bot...")
    
    # Log deployment info for debugging multiple instances
    import os
    service_id = os.getenv('RENDER_SERVICE_ID', 'unknown')
    deploy_id = os.getenv('RENDER_DEPLOY_ID', 'unknown') 
    service_name = os.getenv('RENDER_SERVICE_NAME', 'unknown')
    logger.info(f"🔍 DEPLOYMENT INFO:")
    logger.info(f"  Service ID: {service_id}")
    logger.info(f"  Deploy ID: {deploy_id}")
    logger.info(f"  Service Name: {service_name}")
    logger.info(f"  Instance: {service_id}-{deploy_id}")
    
    # EMERGENCY: Force bot takeover to resolve TelegramConflictError
    logger.info("🚨 EMERGENCY MODE: Performing aggressive bot takeover")
    await force_bot_takeover()
    
    # Give Telegram API time to process the takeover
    logger.info("⏳ Waiting 10 seconds for Telegram API to process takeover...")
    await asyncio.sleep(10)
    
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
    try:
        # Close bot session gracefully
        if hasattr(bot, 'session') and bot.session:
            await bot.session.close()
        
        # Dispose database connections
        if engine:
            await engine.dispose()
            
        logger.info("Bot shutdown completed successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    
    # Small delay to ensure cleanup completes
    await asyncio.sleep(0.5)


async def main():
    """Main function"""
    # Register startup and shutdown hooks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        raise KeyboardInterrupt()
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start polling with retry mechanism for TelegramConflictError
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            logger.info(f"Starting polling... (attempt {retry_count + 1}/{max_retries})")
            await dp.start_polling(bot)
            break  # Success - exit retry loop
        except Exception as e:
            if "TelegramConflictError" in str(e) or "terminated by other getUpdates request" in str(e):
                retry_count += 1
                if retry_count < max_retries:
                    logger.warning(f"TelegramConflictError detected, performing emergency takeover (retry {retry_count}/{max_retries})")
                    await force_bot_takeover()
                    await asyncio.sleep(20)  # Wait longer before retry
                    continue
                else:
                    logger.error("Max retries reached for TelegramConflictError")
                    raise
            elif isinstance(e, KeyboardInterrupt):
                logger.info("Bot stopped by user or signal")
                break
            else:
                logger.error(f"Unexpected error occurred: {e}")
                raise
        except KeyboardInterrupt:
            logger.info("Bot stopped by user or signal")
            break
    
    logger.info("Performing final cleanup...")
    await on_shutdown()


if __name__ == "__main__":
    asyncio.run(main())