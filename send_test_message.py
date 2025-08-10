#!/usr/bin/env python3
"""
Отправка тестового сообщения напрямую
"""
import asyncio
from aiogram import Bot
from dotenv import load_dotenv
import os

load_dotenv()

async def send_test():
    bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
    
    try:
        # Ваш ID из .env
        user_id = 99006770
        
        await bot.send_message(
            chat_id=user_id,
            text="🤖 Тестовое сообщение от бота!\n\nЕсли вы получили это сообщение, то бот работает правильно."
        )
        print("✅ Сообщение отправлено успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
    
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(send_test())