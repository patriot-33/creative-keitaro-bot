"""
OAuth web server for Google Drive authorization
"""

import logging
from datetime import datetime, timedelta
from urllib.parse import urlencode
from aiohttp import web, ClientSession
from aiohttp.web import Request, Response
import aiohttp_cors
import json

import sys
from pathlib import Path

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from core.config import settings
from db.database import get_db_session
from db.models.user import User
from integrations.google.oauth_drive import OAuthGoogleDriveService
from sqlalchemy import select

logger = logging.getLogger(__name__)

# Store pending auth states (user_id -> state)
pending_auth_states = {}

async def start_google_auth(request: Request) -> Response:
    """Initiate Google OAuth flow"""
    try:
        user_id = request.query.get('user_id')
        if not user_id:
            return web.json_response({'error': 'Missing user_id parameter'}, status=400)
        
        # Create OAuth flow
        flow = OAuthGoogleDriveService.create_auth_flow()
        
        # Generate auth URL
        auth_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        
        # Store state for this user
        pending_auth_states[user_id] = state
        
        logger.info(f"Starting Google auth for user {user_id}, state: {state}")
        
        return web.json_response({
            'auth_url': auth_url,
            'state': state,
            'message': 'Visit the auth_url to authorize Google Drive access'
        })
        
    except Exception as e:
        logger.error(f"Error starting Google auth: {e}")
        return web.json_response({'error': str(e)}, status=500)

async def google_callback(request: Request) -> Response:
    """Handle Google OAuth callback"""
    try:
        # Get authorization code and state from callback
        code = request.query.get('code')
        state = request.query.get('state')
        error = request.query.get('error')
        
        if error:
            logger.error(f"OAuth error: {error}")
            return web.Response(
                text=f"<h1>Authorization Failed</h1><p>Error: {error}</p>", 
                content_type='text/html',
                status=400
            )
        
        if not code or not state:
            return web.Response(
                text="<h1>Invalid Request</h1><p>Missing code or state parameter</p>", 
                content_type='text/html',
                status=400
            )
        
        # Find user by state
        user_id = None
        for uid, stored_state in pending_auth_states.items():
            if stored_state == state:
                user_id = uid
                break
        
        if not user_id:
            logger.error(f"No user found for state: {state}")
            return web.Response(
                text="<h1>Invalid State</h1><p>Authorization state not found</p>", 
                content_type='text/html',
                status=400
            )
        
        logger.info(f"Processing OAuth callback for user {user_id}")
        
        # Exchange code for tokens
        flow = OAuthGoogleDriveService.create_auth_flow()
        flow.fetch_token(code=code)
        
        credentials = flow.credentials
        
        # Save tokens to database
        async with get_db_session() as session:
            stmt = select(User).where(User.tg_user_id == int(user_id))
            result = await session.execute(stmt)
            db_user = result.scalar_one_or_none()
            
            if not db_user:
                logger.error(f"User {user_id} not found in database")
                return web.Response(
                    text="<h1>User Not Found</h1><p>Please start bot first</p>", 
                    content_type='text/html',
                    status=404
                )
            
            # Update user with OAuth tokens
            db_user.google_access_token = credentials.token
            db_user.google_refresh_token = credentials.refresh_token
            
            # Set expiry time (tokens typically last 1 hour)
            if credentials.expiry:
                db_user.google_token_expires_at = credentials.expiry
            else:
                # Default to 1 hour from now
                db_user.google_token_expires_at = datetime.utcnow() + timedelta(hours=1)
            
            await session.commit()
            
        # Clean up pending state
        if user_id in pending_auth_states:
            del pending_auth_states[user_id]
        
        logger.info(f"OAuth tokens saved for user {user_id}")
        
        return web.Response(
            text="""
            <h1>✅ Authorization Successful!</h1>
            <p>Google Drive access has been granted.</p>
            <p>You can now close this window and return to the Telegram bot.</p>
            <script>
                setTimeout(() => window.close(), 3000);
            </script>
            """, 
            content_type='text/html'
        )
        
    except Exception as e:
        logger.error(f"Error in Google callback: {e}")
        return web.Response(
            text=f"<h1>Error</h1><p>Authorization failed: {str(e)}</p>", 
            content_type='text/html',
            status=500
        )

async def auth_status(request: Request) -> Response:
    """Check OAuth status for a user"""
    try:
        user_id = request.query.get('user_id')
        if not user_id:
            return web.json_response({'error': 'Missing user_id parameter'}, status=400)
        
        async with get_db_session() as session:
            stmt = select(User).where(User.tg_user_id == int(user_id))
            result = await session.execute(stmt)
            db_user = result.scalar_one_or_none()
            
            if not db_user:
                return web.json_response({'authorized': False, 'error': 'User not found'})
            
            has_tokens = bool(db_user.google_access_token and db_user.google_refresh_token)
            is_expired = False
            
            if has_tokens and db_user.google_token_expires_at:
                is_expired = db_user.google_token_expires_at <= datetime.utcnow()
            
            return web.json_response({
                'authorized': has_tokens,
                'expired': is_expired,
                'expires_at': db_user.google_token_expires_at.isoformat() if db_user.google_token_expires_at else None
            })
            
    except Exception as e:
        logger.error(f"Error checking auth status: {e}")
        return web.json_response({'error': str(e)}, status=500)

def create_oauth_app() -> web.Application:
    """Create OAuth web application"""
    app = web.Application()
    
    # Setup CORS
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
            allow_methods="*"
        )
    })
    
    # Add routes
    app.router.add_get('/auth/google/start', start_google_auth)
    app.router.add_get('/auth/google/callback', google_callback)
    app.router.add_get('/auth/google/status', auth_status)
    
    # Add CORS to all routes
    for route in list(app.router.routes()):
        cors.add(route)
    
    logger.info("OAuth web application created")
    return app

if __name__ == "__main__":
    # For local development
    app = create_oauth_app()
    web.run_app(app, host='0.0.0.0', port=8080)