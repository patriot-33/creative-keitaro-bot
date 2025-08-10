#!/usr/bin/env python3
"""Анализ кликов TR32 за период 06.08.25-10.08.25"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from integrations.keitaro.client import KeitaroClient

async def analyze_tr32_clicks():
    """Показать детальные клики TR32 за 06.08.25-10.08.25"""
    
    print("🔍 TR32 CLICKS ANALYSIS")
    print("=" * 80)
    
    async with KeitaroClient() as client:
        
        # Получаем источники трафика (исключаем Google)
        traffic_sources = await client.get_traffic_sources()
        non_google_ids = [str(ts['id']) for ts in traffic_sources if ts['id'] != 2]
        
        # Период точно как ты просил: 06.08.25-10.08.25
        start_date = '2025-08-06 00:00:00'
        end_date = '2025-08-10 23:59:59'
        
        print(f"📅 Анализ периода: {start_date} - {end_date}")
        print(f"🌐 Источники трафика (не Google): {non_google_ids}")
        print("-" * 60)
        
        # ЗАПРОС 1: Детальные данные TR32 по часам
        detailed_params = {
            'metrics': ['clicks'],
            'columns': ['sub_id_4', 'datetime'],
            'filters': [
                {
                    'name': 'datetime',
                    'operator': 'BETWEEN',
                    'expression': [start_date, end_date]
                },
                {
                    'name': 'sub_id_4',
                    'operator': 'EQUALS',
                    'expression': 'tr32'
                },
                {
                    'name': 'ts_id',
                    'operator': 'IN_LIST',
                    'expression': non_google_ids
                }
            ],
            'grouping': ['sub_id_4', 'datetime'],
            'limit': 10000
        }
        
        print("🔄 Получаем детальные данные TR32...")
        detailed_data = await client._make_request('/admin_api/v1/report/build', method='POST', json=detailed_params)
        
        if not detailed_data or 'rows' not in detailed_data:
            print("❌ Нет детальных данных!")
            return
        
        # Обрабатываем данные
        daily_breakdown = {}
        hourly_data = []
        
        for row in detailed_data['rows']:
            datetime_str = row.get('datetime', '')
            clicks = int(row.get('clicks', 0))
            
            if datetime_str and clicks > 0:
                # Извлекаем дату
                date_part = datetime_str.split('T')[0] if 'T' in datetime_str else datetime_str.split(' ')[0]
                
                # Агрегируем по дням
                if date_part not in daily_breakdown:
                    daily_breakdown[date_part] = 0
                daily_breakdown[date_part] += clicks
                
                # Сохраняем почасовые данные
                hourly_data.append({
                    'datetime': datetime_str,
                    'date': date_part,
                    'clicks': clicks
                })
        
        print(f"✅ Найдено {len(detailed_data['rows'])} строк для TR32")
        print()
        
        # DAILY SUMMARY
        print("📊 TR32 КЛИКИ ПО ДНЯМ:")
        print("-" * 50)
        total_clicks = 0
        active_days = 0
        
        for date in sorted(daily_breakdown.keys()):
            clicks = daily_breakdown[date]
            total_clicks += clicks
            is_active = clicks >= 10
            if is_active:
                active_days += 1
            status = "🟢 АКТИВНЫЙ" if is_active else "🔴 неактивный"
            print(f"{date}: {clicks:3d} кликов - {status}")
        
        print("-" * 50)
        print(f"ИТОГО: {total_clicks} кликов за {len(daily_breakdown)} дней")
        print(f"АКТИВНЫХ ДНЕЙ (10+): {active_days}")
        print()
        
        # HOURLY BREAKDOWN for each day
        print("⏰ ДЕТАЛЬНЫЙ ПОЧАСОВОЙ РАЗБОР:")
        print("=" * 60)
        
        for date in sorted(daily_breakdown.keys()):
            print(f"\n📅 {date} (всего: {daily_breakdown[date]} кликов):")
            day_hours = [h for h in hourly_data if h['date'] == date]
            day_hours.sort(key=lambda x: x['datetime'])
            
            for hour_data in day_hours:
                time_part = hour_data['datetime'].split('T')[1] if 'T' in hour_data['datetime'] else hour_data['datetime'].split(' ')[1]
                print(f"  {time_part}: {hour_data['clicks']} кликов")
        
        print()
        print("🔍 СРАВНЕНИЕ С ОЖИДАНИЯМИ:")
        print("-" * 40)
        your_expectations = {
            '2025-08-10': 51,
            '2025-08-09': 98, 
            '2025-08-08': 85,
            '2025-08-07': 88
        }
        
        for date, expected in your_expectations.items():
            actual = daily_breakdown.get(date, 0)
            diff = actual - expected
            symbol = "📈" if diff > 0 else "📉" if diff < 0 else "🟰"
            print(f"{date}: ожидал {expected:3d}, получил {actual:3d} ({diff:+3d}) {symbol}")
        
        # Check if we have data for 2025-08-06 (which you didn't expect)
        if '2025-08-06' in daily_breakdown:
            print(f"2025-08-06: НЕ ожидал, но есть {daily_breakdown['2025-08-06']} кликов 🆕")
        
        # ЗАПРОС 2: Проверим все клики за период (для сравнения)
        print(f"\n🔬 ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА:")
        print("-" * 40)
        
        all_clicks_params = {
            'metrics': ['clicks', 'global_unique_clicks'],
            'columns': ['sub_id_4'],
            'filters': [
                {
                    'name': 'datetime',
                    'operator': 'BETWEEN',
                    'expression': [start_date, end_date]
                },
                {
                    'name': 'sub_id_4',
                    'operator': 'EQUALS',
                    'expression': 'tr32'
                },
                {
                    'name': 'ts_id',
                    'operator': 'IN_LIST',
                    'expression': non_google_ids
                }
            ],
            'grouping': ['sub_id_4'],
            'limit': 1000
        }
        
        all_clicks_data = await client._make_request('/admin_api/v1/report/build', method='POST', json=all_clicks_params)
        
        if all_clicks_data and 'rows' in all_clicks_data and len(all_clicks_data['rows']) > 0:
            row = all_clicks_data['rows'][0]
            total_all_clicks = row.get('clicks', 0)
            unique_clicks = row.get('global_unique_clicks', 0)
            print(f"Всего кликов TR32 за период: {total_all_clicks}")
            print(f"Уникальных кликов: {unique_clicks}")
            print(f"Соответствие с почасовой агрегацией: {total_clicks == total_all_clicks} {'✅' if total_clicks == total_all_clicks else '❌'}")

if __name__ == "__main__":
    asyncio.run(analyze_tr32_clicks())