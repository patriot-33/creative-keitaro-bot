import asyncio
import logging
import sys
import signal
from pathlib import Path
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.filters import Command
from aiogram.types import Message, Update
from aiogram.fsm.storage.memory import MemoryStorage
from typing import Callable, Dict, Any, Awaitable

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.config import settings
from db.database import engine
from db.models import Base
from bot.handlers import reports, admin, upload, google_auth

# Configure logging with enterprise-level setup
import os

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(funcName)s() - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Set specific loggers to appropriate levels
logging.getLogger('aiogram').setLevel(logging.INFO)
logging.getLogger('aiohttp').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Generate unique instance ID
import time
import uuid
INSTANCE_ID = f"{os.getenv('RENDER_SERVICE_ID', 'local')}-{int(time.time())}-{uuid.uuid4().hex[:8]}"

# Log startup info
logger.info("="*80)
logger.info("BOT STARTUP: main.py loaded")
logger.info(f"INSTANCE ID: {INSTANCE_ID}")
logger.info(f"Python version: {sys.version}")
logger.info(f"Working directory: {os.getcwd()}")
logger.info("="*80)

# Initialize bot and dispatcher (singleton pattern to prevent duplicates)
_bot_instance = None
_dp_instance = None

def get_bot_instance():
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = Bot(token=settings.telegram_bot_token)
    return _bot_instance

def get_dispatcher_instance():
    global _dp_instance
    if _dp_instance is None:
        _dp_instance = Dispatcher(storage=MemoryStorage())
    return _dp_instance

bot = get_bot_instance()
dp = get_dispatcher_instance()


class LoggingMiddleware(BaseMiddleware):
    """Enterprise logging middleware"""
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        # Log all incoming updates
        if event.message:
            msg = event.message
            logger.info(f"INCOMING MESSAGE: user_id={msg.from_user.id}, "
                       f"username={msg.from_user.username}, "
                       f"text='{msg.text}', "
                       f"chat_id={msg.chat.id}, "
                       f"message_id={msg.message_id}")
            
            # Special logging for commands
            if msg.text and msg.text.startswith('/'):
                logger.warning(f"COMMAND RECEIVED: '{msg.text}' from user {msg.from_user.id}")
        
        elif event.callback_query:
            cb = event.callback_query
            logger.info(f"CALLBACK QUERY: user_id={cb.from_user.id}, "
                       f"data='{cb.data}', "
                       f"message_id={cb.message.message_id if cb.message else 'inline'}")
        
        # Continue processing
        return await handler(event, data)


# Register middleware
logger.info("Registering logging middleware...")
dp.update.middleware(LoggingMiddleware())
logger.info("Logging middleware registered")

# Register routers with detailed logging
logger.info("Registering routers...")
logger.info("  - Registering reports router")
dp.include_router(reports.router)
logger.info("  - Registering admin router")
dp.include_router(admin.router)
logger.info("  - Registering upload router")
dp.include_router(upload.router)
logger.info("  - Registering google_auth router")
dp.include_router(google_auth.router)
logger.info("All routers registered successfully")


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
/export - 📊 Экспорт в Google Таблицы
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

/export - Экспорт отчетов в Google Таблицы
  • Типы: Креативы, Байеры, ГЕО
  • Ссылка на Google Sheets

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

async def aggressively_claim_bot_token():
    """Aggressively claim exclusive bot token access"""
    import os
    import aiohttp
    
    logger.info(f"🔥 [{INSTANCE_ID}] Aggressively claiming bot token...")
    
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error('⚠️  No TELEGRAM_BOT_TOKEN found')
        return False
    
    base_url = f'https://api.telegram.org/bot{token}'
    
    try:
        connector = aiohttp.TCPConnector(enable_cleanup_closed=True)
        async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=60)) as session:
            
            # Step 1: Verify bot identity and get current status
            logger.info('🔥 Step 1: Verify bot identity and check current state')
            async with session.get(f'{base_url}/getMe') as resp:
                me_result = await resp.json()
                logger.info(f'  Bot identity: {me_result}')
            
            # Step 2: Get webhook info to understand current state
            logger.info('🔥 Step 2: Check webhook status')
            async with session.get(f'{base_url}/getWebhookInfo') as resp:
                webhook_result = await resp.json()
                logger.info(f'  Webhook info: {webhook_result}')
            
            # Step 3: Multiple aggressive webhook deletions
            logger.info('🔥 Step 3: Aggressive webhook deletion (10 attempts)')
            for attempt in range(10):
                try:
                    async with session.post(f'{base_url}/deleteWebhook', json={'drop_pending_updates': True}) as resp:
                        result = await resp.json()
                        logger.info(f'  Delete attempt {attempt+1}: {result}')
                        if result.get('ok'):
                            # Wait between attempts to ensure processing
                            await asyncio.sleep(2)
                        else:
                            logger.warning(f'  Delete attempt {attempt+1} failed: {result}')
                except Exception as e:
                    logger.warning(f'  Delete attempt {attempt+1} exception: {e}')
                
            # Longer wait after webhook operations
            logger.info('⏳ Waiting 10 seconds after webhook cleanup...')
            await asyncio.sleep(10)
            
            # Step 4: Exhaust update queue with multiple strategies
            logger.info('🔥 Step 4: Exhaust update queue (multiple strategies)')
            
            # Strategy 1: High offset clear
            for attempt in range(3):
                try:
                    async with session.post(f'{base_url}/getUpdates', json={'offset': 999999999, 'limit': 1, 'timeout': 0}) as resp:
                        result = await resp.json()
                        logger.info(f'  High offset attempt {attempt+1}: {result}')
                        if result.get('ok'):
                            break
                except Exception as e:
                    logger.warning(f'  High offset attempt {attempt+1} failed: {e}')
                await asyncio.sleep(2)
                
            await asyncio.sleep(5)
            
            # Strategy 2: Progressive queue exhaustion
            logger.info('🔥 Step 5: Progressive queue exhaustion')
            for i in range(20):  # Up to 20 attempts
                try:
                    async with session.post(f'{base_url}/getUpdates', json={'offset': -1, 'limit': 100, 'timeout': 0}) as resp:
                        result = await resp.json()
                        if result.get('ok'):
                            updates_count = len(result.get('result', []))
                            logger.info(f'  Queue check {i+1}: Got {updates_count} updates')
                            if updates_count == 0:
                                logger.info('  ✅ Queue is empty!')
                                break
                        else:
                            # If we get an error, it might mean the queue is being accessed by another instance
                            logger.warning(f'  Queue check {i+1} error: {result}')
                            if 'conflict' in str(result).lower():
                                logger.error('  🚨 CONFLICT DETECTED - another instance is active!')
                                # Continue anyway to try to claim the token
                except Exception as e:
                    logger.warning(f'  Queue check {i+1} exception: {e}')
                
                await asyncio.sleep(1)
            
            # Step 6: Final aggressive webhook cleanup
            logger.info('🔥 Step 6: Final aggressive webhook cleanup')
            for attempt in range(5):
                try:
                    async with session.post(f'{base_url}/deleteWebhook', json={'drop_pending_updates': True}) as resp:
                        result = await resp.json()
                        logger.info(f'  Final cleanup {attempt+1}: {result}')
                except Exception as e:
                    logger.warning(f'  Final cleanup {attempt+1} failed: {e}')
                await asyncio.sleep(1)
            
            # Step 7: Extended waiting period for Telegram API to stabilize
            logger.info('⏳ Extended wait for Telegram API stabilization (60 seconds)...')
            await asyncio.sleep(60)  # Much longer wait
            
            logger.info(f'✅ [{INSTANCE_ID}] Bot token claim completed')
            return True
            
    except Exception as e:
        logger.error(f'❌ Bot token claim failed: {e}')
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
    
    # Aggressively claim bot token to ensure exclusive access
    logger.info(f"🔥 [{INSTANCE_ID}] Claiming exclusive bot token access...")
    await aggressively_claim_bot_token()
    
    # Give Telegram API time to process the takeover
    logger.info("⏳ Waiting 10 seconds for Telegram API to process takeover...")
    await asyncio.sleep(10)
    
    # Load users from database
    await load_users_from_database()
    
    # Ensure all owners from settings exist in database
    try:
        from bot.handlers.admin import ensure_owners_in_database
        await ensure_owners_in_database()
        logger.info("Owner synchronization completed!")
    except Exception as e:
        logger.warning(f"Owner synchronization failed: {e}")
    
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
                    logger.warning(f"TelegramConflictError detected, aggressively reclaiming token (retry {retry_count}/{max_retries})")
                    await aggressively_claim_bot_token()
                    await asyncio.sleep(60)  # Wait even longer before retry
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