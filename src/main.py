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
        
        # Start web server
        port = 8080  # OAuth server port
        runner = web.AppRunner(oauth_app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        
        logger.info(f"OAuth server started on port {port}")
        
        # Start Telegram bot
        logger.info("Starting Telegram bot...")
        await bot_main()
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    asyncio.run(main())