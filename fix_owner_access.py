#!/usr/bin/env python3
"""
Экстренное исправление доступа owner через REST API
"""

import requests
import asyncio
import os

def add_owner_via_api():
    """Добавление owner через прямой SQL запрос"""
    
    # Получаем DATABASE_URL из переменных окружения
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not found")
        return
    
    print(f"Database URL: {database_url}")
    
    # SQL запрос для добавления owner
    sql_commands = [
        # Добавляем первого owner (99006770)
        """
        INSERT INTO users (tg_user_id, tg_username, full_name, role, buyer_id, is_active, created_at, updated_at)
        VALUES (99006770, 'owner1', 'Owner 1', 'owner', NULL, true, NOW(), NOW())
        ON CONFLICT (tg_user_id) 
        DO UPDATE SET role = 'owner', is_active = true, updated_at = NOW();
        """,
        
        # Добавляем второго owner (115031094)
        """
        INSERT INTO users (tg_user_id, tg_username, full_name, role, buyer_id, is_active, created_at, updated_at)
        VALUES (115031094, 'owner2', 'Owner 2', 'owner', NULL, true, NOW(), NOW())
        ON CONFLICT (tg_user_id) 
        DO UPDATE SET role = 'owner', is_active = true, updated_at = NOW();
        """
    ]
    
    print("SQL commands to execute:")
    for cmd in sql_commands:
        print(cmd)
    
    print("\n❗ Выполните эти команды на Render.com через psql:")
    print("1. Зайдите в Render Dashboard")
    print("2. Перейдите в ваш PostgreSQL сервис") 
    print("3. Выполните команды выше через psql Shell")
    print("4. Или выполните их через админ-панель PostgreSQL")

if __name__ == "__main__":
    add_owner_via_api()