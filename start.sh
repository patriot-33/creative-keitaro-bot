#!/bin/bash

# Exit on any error
set -e

echo "🚀 Starting Creative Keitaro Bot..."
echo "Environment: ${APP_ENV:-production}"
echo "Service ID: ${RENDER_SERVICE_ID:-local}"
echo "Deploy ID: ${RENDER_DEPLOY_ID:-local}"
echo "Service Name: ${RENDER_SERVICE_NAME:-unknown}"
echo "Bot Token (last 8 chars): ...${TELEGRAM_BOT_TOKEN: -8}"

# Check for force takeover mode
if [ "$FORCE_BOT_TAKEOVER" = "true" ]; then
    echo "⚠️  FORCE_BOT_TAKEOVER mode enabled - will aggressively claim bot"
fi

# Function to check if PostgreSQL is ready
wait_for_postgres() {
    echo "⏳ Waiting for PostgreSQL to be ready..."
    
    # Extract connection details from DATABASE_URL if available
    if [ -n "$DATABASE_URL" ]; then
        # Use python to extract host and port from DATABASE_URL
        python3 -c "
import urllib.parse as up
import os
import socket
import time

url = os.environ.get('DATABASE_URL', '')
if url:
    parsed = up.urlparse(url)
    host = parsed.hostname or 'localhost'
    port = parsed.port or 5432
    
    max_retries = 30
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                print(f'✅ PostgreSQL is ready at {host}:{port}')
                exit(0)
            else:
                print(f'⏳ PostgreSQL not ready at {host}:{port}, retrying... ({retry_count + 1}/{max_retries})')
        except Exception as e:
            print(f'⏳ Connection attempt failed: {e}, retrying... ({retry_count + 1}/{max_retries})')
        
        retry_count += 1
        time.sleep(2)
    
    print(f'❌ Failed to connect to PostgreSQL after {max_retries} attempts')
    exit(1)
else:
    print('⚠️  No DATABASE_URL found, skipping PostgreSQL check')
"
    else
        echo "⚠️  No DATABASE_URL found, skipping PostgreSQL check"
    fi
}

# Function to run database migrations
run_migrations() {
    echo "🔄 Running database migrations..."
    
    # Check if alembic.ini exists
    if [ -f "alembic.ini" ]; then
        # Create alembic_logs directory if it doesn't exist
        mkdir -p alembic_logs
        
        # Run migrations
        python3 -c "
import asyncio
import logging
from alembic.config import Config
from alembic import command
from src.core.config import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('alembic.runtime.migration')

try:
    # Configure alembic
    alembic_cfg = Config('alembic.ini')
    alembic_cfg.set_main_option('sqlalchemy.url', settings.database_url)
    
    # Run upgrade to head
    command.upgrade(alembic_cfg, 'head')
    print('✅ Database migrations completed successfully')
except Exception as e:
    print(f'❌ Migration failed: {e}')
    print('⚠️  Continuing without migrations...')
"
    else
        echo "⚠️  alembic.ini not found, skipping migrations"
    fi
}

# Function to cleanup previous bot instances
cleanup_previous_instances() {
    echo "🧹 Cleaning up previous bot instances..."
    
    # Method 1: Try pkill if available
    if command -v pkill >/dev/null 2>&1; then
        echo "🔍 Using pkill to find and terminate bot processes..."
        pkill -f "python.*src.bot.main" 2>/dev/null || true
        pkill -f "python.*main.py" 2>/dev/null || true
        pkill -f "creative.*bot" 2>/dev/null || true
        sleep 2
        # Force kill if still running
        pkill -9 -f "python.*src.bot.main" 2>/dev/null || true
        pkill -9 -f "python.*main.py" 2>/dev/null || true
        pkill -9 -f "creative.*bot" 2>/dev/null || true
    fi
    
    # Method 2: Use ps and kill (works in most containers)
    echo "🔍 Using ps/kill to cleanup remaining processes..."
    if command -v ps >/dev/null 2>&1; then
        # Find Python processes related to the bot
        PIDS=$(ps aux 2>/dev/null | grep -E "python.*src\.bot\.main|python.*main\.py|python.*creative.*bot" | grep -v grep | awk '{print $2}' || true)
        if [ ! -z "$PIDS" ]; then
            echo "🎯 Found processes to kill: $PIDS"
            echo "$PIDS" | xargs -r kill -TERM 2>/dev/null || true
            sleep 2
            echo "$PIDS" | xargs -r kill -9 2>/dev/null || true
        else
            echo "👍 No bot processes found"
        fi
    fi
    
    # Method 3: Try to find Python processes using different approaches
    echo "🔍 Final cleanup check..."
    if command -v pgrep >/dev/null 2>&1; then
        PYTHON_PIDS=$(pgrep -f "python.*bot" 2>/dev/null || true)
        if [ ! -z "$PYTHON_PIDS" ]; then
            echo "🎯 Found remaining Python bot processes: $PYTHON_PIDS"
            echo "$PYTHON_PIDS" | xargs -r kill -9 2>/dev/null || true
        fi
    fi
    
    # Extra safety: kill any process listening on our expected ports
    if command -v lsof >/dev/null 2>&1; then
        echo "🔍 Checking for processes on port 8000..."
        PORT_PIDS=$(lsof -ti:8000 2>/dev/null || true)
        if [ ! -z "$PORT_PIDS" ]; then
            echo "🎯 Found processes on port 8000: $PORT_PIDS"
            echo "$PORT_PIDS" | xargs -r kill -9 2>/dev/null || true
        fi
    fi
    
    sleep 1
    echo "✅ Previous instances cleaned up"
}

# Function to check if this is a duplicate service
check_duplicate_service() {
    echo "🔍 Checking for duplicate services..."
    
    # Check if we have service info
    if [ -n "$RENDER_SERVICE_ID" ]; then
        echo "This deployment:"
        echo "  Service ID: $RENDER_SERVICE_ID" 
        echo "  Deploy ID: ${RENDER_DEPLOY_ID:-unknown}"
        echo "  Service Name: ${RENDER_SERVICE_NAME:-unknown}"
        
        # Add a unique identifier to prevent conflicts
        export BOT_INSTANCE_ID="${RENDER_SERVICE_ID}-${RENDER_DEPLOY_ID:-$(date +%s)}"
        echo "  Bot Instance ID: $BOT_INSTANCE_ID"
    else
        export BOT_INSTANCE_ID="local-$(date +%s)"
        echo "  Bot Instance ID: $BOT_INSTANCE_ID (local)"
    fi
}

# Function to check for running bot instances via Telegram API
check_bot_instances() {
    echo "🕵️ Checking for other bot instances via Telegram API..."
    
    python3 -c "
import asyncio
import aiohttp
import os

async def check_instances():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        print('⚠️  No TELEGRAM_BOT_TOKEN found')
        return
    
    base_url = f'https://api.telegram.org/bot{token}'
    
    try:
        connector = aiohttp.TCPConnector(enable_cleanup_closed=True)
        async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=10)) as session:
            
            # Check webhook info
            print('📍 Checking current webhook status...')
            async with session.get(f'{base_url}/getWebhookInfo') as resp:
                if resp.status == 200:
                    webhook_info = await resp.json()
                    result = webhook_info.get('result', {})
                    webhook_url = result.get('url', '')
                    pending_updates = result.get('pending_update_count', 0)
                    last_error = result.get('last_error_message', '')
                    print(f'  Webhook URL: {webhook_url or \"(none)\"}')
                    print(f'  Pending updates: {pending_updates}')
                    if last_error:
                        print(f'  Last error: {last_error}')
                else:
                    print(f'❌ Failed to get webhook info: {resp.status}')
            
            # Get bot info
            print('🤖 Checking bot information...')
            async with session.get(f'{base_url}/getMe') as resp:
                if resp.status == 200:
                    bot_info = await resp.json()
                    result = bot_info.get('result', {})
                    print(f'  Bot: @{result.get(\"username\", \"unknown\")} (ID: {result.get(\"id\", \"unknown\")})')
                    print(f'  Name: {result.get(\"first_name\", \"unknown\")}')
                
    except Exception as e:
        print(f'❌ Failed to check bot instances: {e}')

asyncio.run(check_instances())
" || true
}

# Function to aggressively claim bot (force takeover)
force_bot_takeover() {
    echo "💪 Attempting aggressive bot takeover..."
    
    python3 -c "
import asyncio
import aiohttp
import os

async def force_takeover():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        print('⚠️  No TELEGRAM_BOT_TOKEN found')
        return False
    
    base_url = f'https://api.telegram.org/bot{token}'
    
    try:
        connector = aiohttp.TCPConnector(enable_cleanup_closed=True)
        async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=20)) as session:
            
            print('🔥 Step 1: Force delete webhook with max drop_pending_updates')
            async with session.post(f'{base_url}/deleteWebhook', json={'drop_pending_updates': True}) as resp:
                result = await resp.json()
                print(f'  Result: {result}')
                
            await asyncio.sleep(3)
            
            print('🔥 Step 2: Aggressive getUpdates with high offset to skip all')
            async with session.post(f'{base_url}/getUpdates', json={'offset': 999999999, 'limit': 1, 'timeout': 0}) as resp:
                result = await resp.json()
                print(f'  Result: {result}')
                
            await asyncio.sleep(2)
            
            print('🔥 Step 3: Multiple rapid getUpdates to exhaust the queue')
            for i in range(10):
                print(f'    Rapid getUpdates #{i+1}...')
                async with session.post(f'{base_url}/getUpdates', json={'offset': -1, 'limit': 100, 'timeout': 0}) as resp:
                    result = await resp.json()
                    updates_count = len(result.get('result', []))
                    print(f'      Got {updates_count} updates')
                    if updates_count == 0:
                        break
                await asyncio.sleep(0.1)
            
            print('🔥 Step 4: Set webhook to dummy URL to block other instances')
            dummy_url = 'https://httpbin.org/status/200'  # Safe dummy webhook
            async with session.post(f'{base_url}/setWebhook', json={'url': dummy_url, 'drop_pending_updates': True}) as resp:
                result = await resp.json()
                print(f'  Dummy webhook set: {result}')
            
            await asyncio.sleep(3)
            
            print('🔥 Step 5: Remove dummy webhook and go to polling')
            async with session.post(f'{base_url}/deleteWebhook', json={'drop_pending_updates': True}) as resp:
                result = await resp.json()
                print(f'  Dummy webhook removed: {result}')
            
            print('✅ Bot takeover completed')
            return True
            
    except Exception as e:
        print(f'❌ Bot takeover failed: {e}')
        return False

success = asyncio.run(force_takeover())
exit(0 if success else 1)
" || echo "⚠️  Force takeover had issues but continuing..."
}

# Function to reset Telegram webhook
reset_telegram_webhook() {
    echo "🔄 Resetting Telegram webhook to ensure clean start..."
    
    # First, try to delete webhook with drop_pending_updates
    python3 -c "
import asyncio
import aiohttp
import os
import sys
import time

async def reset_webhook():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        print('⚠️  No TELEGRAM_BOT_TOKEN found, skipping webhook reset')
        return False
    
    base_url = f'https://api.telegram.org/bot{token}'
    
    try:
        connector = aiohttp.TCPConnector(enable_cleanup_closed=True)
        async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=15)) as session:
            
            # Step 1: Delete webhook with drop_pending_updates
            print('🧹 Deleting webhook and dropping pending updates...')
            async with session.post(f'{base_url}/deleteWebhook', json={'drop_pending_updates': True}) as resp:
                result1 = await resp.json()
                if resp.status == 200:
                    print(f'✅ Webhook deleted: {result1.get(\"description\", \"OK\")}')
                else:
                    print(f'⚠️  Delete webhook failed: {result1}')
            
            # Wait a moment
            await asyncio.sleep(2)
            
            # Step 2: Use getUpdates to clear any remaining updates (multiple attempts)
            print('🧹 Clearing remaining updates with getUpdates...')
            for attempt in range(3):
                print(f'  Attempt {attempt + 1}/3...')
                async with session.post(f'{base_url}/getUpdates', json={'offset': -1, 'limit': 1, 'timeout': 0}) as resp:
                    result2 = await resp.json()
                    if resp.status == 200:
                        updates_count = len(result2.get('result', []))
                        print(f'  ✅ GetUpdates cleared: got {updates_count} updates')
                        if updates_count == 0:
                            break
                    else:
                        print(f'  ⚠️  GetUpdates failed: {result2}')
                await asyncio.sleep(0.5)
            
            # Wait another moment
            await asyncio.sleep(2)
            
            # Step 3: Set webhook to empty (extra cleanup)
            print('🧹 Final webhook cleanup...')
            async with session.post(f'{base_url}/setWebhook', json={'url': '', 'drop_pending_updates': True}) as resp:
                result3 = await resp.json()
                if resp.status == 200:
                    print(f'✅ Webhook cleared: {result3.get(\"description\", \"OK\")}')
                else:
                    print(f'⚠️  Set empty webhook failed: {result3}')
            
            return True
            
    except Exception as e:
        print(f'❌ Webhook reset failed with exception: {e}')
        return False

# Run the reset
success = asyncio.run(reset_webhook())
if success:
    print('✅ Telegram webhook reset completed')
    exit(0)
else:
    print('⚠️  Webhook reset had issues, but continuing...')
    exit(1)
" && echo "✅ Webhook reset successful" || echo "⚠️  Webhook reset had issues but continuing..."
}

# Function to start the health check server
start_health_server() {
    echo "🏥 Starting health check server..."
    
    # Create a simple health check endpoint
    python3 -c "
import asyncio
import aiohttp.web
import logging
import os
from aiohttp import web

async def health_check(request):
    return web.json_response({'status': 'healthy', 'service': 'creative-keitaro-bot'})

async def start_health_server():
    app = web.Application()
    app.router.add_get('/health', health_check)
    app.router.add_get('/healthz', health_check)
    
    port = int(os.environ.get('PORT', 8000))
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f'🏥 Health server started on port {port}')
    return runner

# Start the health server in background
async def main():
    runner = await start_health_server()
    try:
        # Keep the health server running
        while True:
            await asyncio.sleep(3600)  # Sleep for 1 hour
    except KeyboardInterrupt:
        await runner.cleanup()

if __name__ == '__main__':
    asyncio.run(main())
" &

    HEALTH_PID=$!
    echo "🏥 Health check server started with PID: $HEALTH_PID"
}

# Main execution flow
main() {
    # Step 0: Check for duplicate services
    check_duplicate_service
    
    # Step 1: Check what's currently running
    check_bot_instances
    
    # Step 2: Clean up any previous instances first
    cleanup_previous_instances
    
    # Step 3: Reset Telegram webhook to avoid conflicts
    if [ "$FORCE_BOT_TAKEOVER" = "true" ]; then
        force_bot_takeover
    else
        reset_telegram_webhook
    fi
    
    # Step 4: Give Telegram API extra time to process webhook reset
    echo "⏳ Waiting for Telegram API to process webhook reset..."
    echo "  This may take up to 10 seconds for Telegram to fully process..."
    sleep 10
    
    # Step 5: Final check before starting
    echo "🔍 Final check before starting bot..."
    check_bot_instances
    
    # Wait for PostgreSQL
    wait_for_postgres
    
    # Run migrations
    run_migrations
    
    # Start health check server in background
    start_health_server
    
    # Start the main bot application
    echo "🤖 Starting Telegram bot..."
    exec python3 -m src.bot.main
}

# Trap SIGTERM and SIGINT to clean up properly
cleanup() {
    echo "🛑 Shutting down gracefully..."
    if [ ! -z "$HEALTH_PID" ]; then
        kill $HEALTH_PID 2>/dev/null || true
    fi
    exit 0
}

trap cleanup SIGTERM SIGINT

# Run main function
main