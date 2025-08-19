from typing import List, Optional, Dict, Any
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator
import json


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow",  # Allow extra fields
    )

    # Telegram
    telegram_bot_token: str
    
    # Google (optional - deprecated in favor of Telegram storage)
    google_project_id: Optional[str] = None
    google_service_account_json: Optional[str] = None
    google_drive_root_folder_id: Optional[str] = None
    google_sheets_manifest_id: Optional[str] = None
    google_drive_shared_email: Optional[str] = None
    google_sheets_reuse_spreadsheet_id: Optional[str] = None
    
    # Google OAuth (optional - deprecated in favor of Telegram storage)
    google_oauth_client_id: Optional[str] = None
    google_oauth_client_secret: Optional[str] = None
    google_oauth_redirect_uri: str = "https://creative-keitaro-bot.onrender.com/auth/google/callback"
    
    # Keitaro
    keitaro_base_url: str
    keitaro_api_token: str
    
    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "creative_bot"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    database_url: Optional[str] = None
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # Application
    app_env: str = "development"
    log_level: str = "INFO"
    tz: str = "Europe/Moscow"
    secret_key: str
    
    # Initial whitelist
    allowed_users: Any = ""
    
    # File upload
    max_file_size_mb: int = 50
    allowed_extensions: List[str] = Field(
        default_factory=lambda: ["jpg", "jpeg", "png", "mp4", "mov"]
    )
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # Worker
    worker_concurrency: int = 4
    
    # Cache settings
    cache_ttl_seconds: int = 120
    cache_ttl_reports: int = 300
    
    # Limits
    max_creatives_per_geo_per_day: int = 999
    max_export_rows: int = 100000
    
    # Digest settings
    digest_hour: int = 10
    digest_minute: int = 0
    
    # Creative storage settings (канал для хранения креативов)
    creative_storage_channel_id: Optional[str] = None
    
    # Required subscription settings (обязательная подписка)
    required_channel_id: Optional[str] = None
    required_channel_username: Optional[str] = None
    required_channel_invite_link: Optional[str] = None
    
    @validator("database_url", pre=True, always=True)
    def build_database_url(cls, v, values):
        if v:
            # Render.com provides DATABASE_URL, ensure it uses asyncpg driver
            if v.startswith('postgres://'):
                # Convert postgres:// to postgresql+asyncpg://
                return v.replace('postgres://', 'postgresql+asyncpg://', 1)
            elif v.startswith('postgresql://') and 'asyncpg' not in v:
                # Add asyncpg driver to postgresql:// URLs
                return v.replace('postgresql://', 'postgresql+asyncpg://', 1)
            return v
        return (
            f"postgresql+asyncpg://{values.get('postgres_user')}:"
            f"{values.get('postgres_password')}@{values.get('postgres_host')}:"
            f"{values.get('postgres_port')}/{values.get('postgres_db')}"
        )
    
    @validator("allowed_users", pre=True)
    def parse_allowed_users(cls, v):
        """Parse initial whitelist from string format
        Format: tg_id:role:buyer_id:username
        Example: 99006770:owner::PlantatorBob,115031094:owner::username2
        """
        if isinstance(v, dict):
            return v  # Already parsed
        if not v:
            return {}
        
        users = {}
        for user_str in v.split(","):
            if not user_str.strip():
                continue
            parts = user_str.strip().split(":")
            if len(parts) >= 2:
                tg_id = int(parts[0])
                role = parts[1]
                buyer_id = parts[2] if len(parts) > 2 and parts[2] else None
                username = parts[3] if len(parts) > 3 and parts[3] else None
                users[tg_id] = {
                    "role": role, 
                    "buyer_id": buyer_id,
                    "username": username,
                    "is_approved": True
                }
        return users
    
    @property
    def google_credentials_dict(self) -> Optional[Dict]:
        """Load Google service account credentials (deprecated - use Telegram storage)"""
        if not self.google_service_account_json:
            return None
        if self.google_service_account_json.startswith("{"):
            # JSON string
            return json.loads(self.google_service_account_json)
        else:
            # File path
            with open(self.google_service_account_json, "r") as f:
                return json.load(f)
    
    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024


settings = Settings()