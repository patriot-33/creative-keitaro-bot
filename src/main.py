"""
Main entry point that starts both Telegram bot and OAuth web server
"""

import asyncio
import logging
from aiohttp import web
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from bot.main import main as bot_main
from web.oauth_server import create_oauth_app

logger = logging.getLogger(__name__)

async def main():
    """Main function that runs both bot and OAuth server"""
    try:
        # Create OAuth web app
        oauth_app = create_oauth_app()
        
        # Start OAuth web server on internal port
        oauth_port = 8081  # OAuth server on different port
        oauth_runner = web.AppRunner(oauth_app)
        await oauth_runner.setup()
        oauth_site = web.TCPSite(oauth_runner, '0.0.0.0', oauth_port)
        await oauth_site.start()
        
        logger.info(f"OAuth server started on port {oauth_port}")
        
        # Start health check server on Render port
        import os
        health_port = int(os.environ.get('PORT', 8000))
        health_app = web.Application()
        health_app.router.add_get('/health', health_check)
        health_app.router.add_get('/healthz', health_check)
        
        health_runner = web.AppRunner(health_app)
        await health_runner.setup()
        health_site = web.TCPSite(health_runner, '0.0.0.0', health_port)
        await health_site.start()
        
        logger.info(f"Health server started on port {health_port}")
        
        # Start Telegram bot
        logger.info("Starting Telegram bot...")
        await bot_main()
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise

async def health_check(request):
    """Health check endpoint"""
    return web.json_response({
        'status': 'healthy', 
        'service': 'creative-keitaro-bot',
        'components': {
            'bot': 'running',
            'oauth': 'running',
            'health': 'running'
        }
    })

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    asyncio.run(main())