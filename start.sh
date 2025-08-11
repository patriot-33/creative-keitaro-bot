#!/bin/bash

# Exit on any error
set -e

echo "🚀 Starting Creative Keitaro Bot..."
echo "Environment: ${APP_ENV:-production}"

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
            
            # Step 2: Use getUpdates to clear any remaining updates
            print('🧹 Clearing remaining updates with getUpdates...')
            async with session.post(f'{base_url}/getUpdates', json={'offset': -1, 'limit': 1, 'timeout': 0}) as resp:
                result2 = await resp.json()
                if resp.status == 200:
                    print(f'✅ GetUpdates cleared: got {len(result2.get(\"result\", []))} updates')
                else:
                    print(f'⚠️  GetUpdates failed: {result2}')
            
            # Wait another moment
            await asyncio.sleep(1)
            
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
    # Clean up any previous instances first
    cleanup_previous_instances
    
    # Reset Telegram webhook to avoid conflicts
    reset_telegram_webhook
    
    # Give Telegram API extra time to process webhook reset
    echo "⏳ Waiting for Telegram API to process webhook reset..."
    sleep 5
    
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