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