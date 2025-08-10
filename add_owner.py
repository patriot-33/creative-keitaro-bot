#!/usr/bin/env python3
"""
Скрипт для добавления owner пользователя в базу данных
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(project_root / 'src'))

async def add_owner():
    """Добавление owner в базу данных"""
    try:
        from db.database import get_db_session
        from db.models.user import User
        from core.enums import UserRole
        from sqlalchemy import select
        
        user_id = 115031094
        
        async with get_db_session() as session:
            # Проверяем, существует ли пользователь
            result = await session.execute(select(User).where(User.tg_user_id == user_id))
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                # Обновляем роль на owner
                existing_user.role = UserRole.OWNER
                existing_user.is_active = True
                print(f"Updated existing user {user_id} to owner")
            else:
                # Создаем нового owner
                new_user = User(
                    tg_user_id=user_id,
                    tg_username='',
                    full_name='Owner',
                    role=UserRole.OWNER,
                    buyer_id=None,
                    is_active=True
                )
                session.add(new_user)
                print(f"Created new owner user {user_id}")
            
            await session.commit()
            print("✅ Owner added successfully")
            
    except Exception as e:
        print(f"❌ Failed to add owner: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(add_owner())