#!/usr/bin/env python3
"""
Стабильный бот для постоянной работы
"""
import asyncio
import aiohttp
from dotenv import load_dotenv
import os
import json
from datetime import datetime

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = 99006770
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

def log(message):
    """Логирование с временем"""
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {message}")

async def send_message(chat_id, text):
    """Отправка сообщения"""
    async with aiohttp.ClientSession() as session:
        url = f"{BASE_URL}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        
        try:
            async with session.post(url, json=data) as response:
                result = await response.json()
                if result.get('ok'):
                    log(f"✅ Отправлено: {text[:50]}...")
                    return True
                else:
                    log(f"❌ Ошибка отправки: {result.get('description', 'неизвестная')}")
                    return False
        except Exception as e:
            log(f"❌ Исключение: {e}")
            return False

async def get_updates(offset=0):
    """Получение обновлений"""
    async with aiohttp.ClientSession() as session:
        url = f"{BASE_URL}/getUpdates"
        params = {"offset": offset, "timeout": 10}
        
        try:
            async with session.get(url, params=params) as response:
                data = await response.json()
                if data.get('ok'):
                    return data['result']
                else:
                    log(f"❌ Ошибка API: {data.get('description', 'неизвестная')}")
                    return []
        except Exception as e:
            log(f"❌ Ошибка сети: {e}")
            return []

async def process_message(message):
    """Обработка входящего сообщения"""
    user_id = message['from']['id']
    username = message['from'].get('username', 'без_username')
    text = message.get('text', '')
    chat_id = message['chat']['id']
    
    log(f"📨 От @{username} ({user_id}): {text}")
    
    # Проверка доступа
    if user_id != ALLOWED_USER_ID:
        await send_message(chat_id, f"❌ Доступ запрещен\\n\\nВаш ID: {user_id}\\nТребуется: {ALLOWED_USER_ID}")
        return
    
    # Обработка команд
    if text == '/start':
        response = f"""🤖 <b>CreativeKeitaroBot запущен!</b>

👋 Привет!
🆔 Ваш ID: <code>{user_id}</code>
👤 Роль: <b>Владелец</b>
⏰ Время: {datetime.now().strftime('%H:%M:%S')}

📋 <b>Доступные команды:</b>
/start - Перезапуск бота
/help - Подробная справка
/status - Статус системы
/ping - Проверка связи

✅ Бот работает стабильно на HTTP API"""
        
        await send_message(chat_id, response)
        
    elif text == '/help':
        response = """📖 <b>Полная справка CreativeKeitaroBot</b>

🔧 <b>Основные команды:</b>
/start - Запуск и приветствие
/help - Эта справка
/status - Проверка состояния бота
/ping - Быстрая проверка связи

📊 <b>Функции (в разработке):</b>
• Загрузка креативов в Google Drive
• Интеграция с Keitaro API
• Статистика и отчеты
• Управление командой

🛠 <b>Техническая информация:</b>
• Версия: 1.0 HTTP API
• База данных: SQLite
• Статус: В разработке

📧 <b>Поддержка:</b> @PlantatorBob"""
        
        await send_message(chat_id, response)
        
    elif text == '/status':
        response = f"""📊 <b>Статус системы</b>

🟢 Бот: <b>Работает</b>
🌐 API: <b>Подключен</b>
⏰ Время: <code>{datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</code>
🔄 Режим: <b>HTTP Polling</b>

✅ Все системы функционируют нормально"""
        
        await send_message(chat_id, response)
        
    elif text == '/ping':
        await send_message(chat_id, "🏓 Pong! Бот отвечает быстро.")
        
    elif text.startswith('/'):
        await send_message(chat_id, f"❓ Неизвестная команда: {text}\\n\\nИспользуйте /help для списка команд")
        
    else:
        # Эхо для обычных сообщений
        await send_message(chat_id, f"📝 Получил сообщение: <i>{text}</i>\\n\\n💡 Используйте команды /start или /help")

async def main():
    log("🚀 Запуск стабильного CreativeKeitaroBot...")
    log(f"🔑 Токен: {TOKEN[:20]}...")
    log(f"👤 Разрешенный пользователь: {ALLOWED_USER_ID}")
    
    offset = 0
    error_count = 0
    
    # Основной цикл
    while True:
        try:
            updates = await get_updates(offset)
            
            if updates:
                log(f"📥 Получено {len(updates)} обновлений")
                error_count = 0  # Сброс счетчика ошибок при успехе
                
                for update in updates:
                    if 'message' in update:
                        await process_message(update['message'])
                    
                    offset = update['update_id'] + 1
            
            # Небольшая пауза между проверками
            await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            log("⛔ Бот остановлен пользователем")
            break
            
        except Exception as e:
            error_count += 1
            log(f"❌ Ошибка #{error_count}: {e}")
            
            if error_count >= 10:
                log("💥 Критическое количество ошибок. Увеличиваю паузу...")
                await asyncio.sleep(30)
                error_count = 0
            else:
                await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\\n👋 До свидания!")
    except Exception as e:
        print(f"💥 Критическая ошибка: {e}")