#!/usr/bin/env python3
"""
Глубокое сравнение API данных с CSV
Проверяем гипотезы о расхождениях
"""

import asyncio
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

# Добавляем путь к проекту
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from integrations.keitaro.client import KeitaroClient

async def deep_comparison_api_vs_csv():
    """Глубокое сравнение API и CSV данных"""
    
    print("🔬 ГЛУБОКОЕ СРАВНЕНИЕ API VS CSV")
    print("=" * 60)
    
    # 1. Загружаем и анализируем CSV данные
    print("📊 АНАЛИЗ CSV ДАННЫХ:")
    
    try:
        # Клики
        clicks_df = pd.read_csv("n1 clicks yesterday.csv", sep=";", encoding='utf-8')
        n1_clicks = clicks_df[clicks_df['Sub ID 1'] == 'n1']
        
        # Конверсии
        conversions_df = pd.read_csv("n1 conversions 050825.csv", sep=";", encoding='utf-8')
        n1_conversions = conversions_df[conversions_df['Sub ID 1'] == 'n1']
        
        print(f"   CSV Клики n1: {len(n1_clicks)}")
        print(f"   CSV Конверсии n1: {len(n1_conversions)}")
        
        # Анализ external_id в CSV
        csv_external_ids = set(n1_conversions['External ID'].dropna().values)
        print(f"   CSV Уникальные External ID: {len(csv_external_ids)}")
        
        # Анализ типов конверсий в CSV
        csv_leads = len(n1_conversions[n1_conversions['Статус'] == 'lead'])
        csv_sales = len(n1_conversions[n1_conversions['Статус'] == 'sale'])
        
        print(f"   CSV Лиды: {csv_leads}")
        print(f"   CSV Продажи: {csv_sales}")
        
        # Временные диапазоны в CSV
        n1_conversions['Время конверсии'] = pd.to_datetime(n1_conversions['Время конверсии'])
        csv_min_time = n1_conversions['Время конверсии'].min()
        csv_max_time = n1_conversions['Время конверсии'].max()
        
        print(f"   CSV Время от: {csv_min_time}")
        print(f"   CSV Время до: {csv_max_time}")
        
    except Exception as e:
        print(f"❌ Ошибка загрузки CSV: {e}")
        return
    
    # 2. Получаем данные через API
    print(f"\n🌐 АНАЛИЗ API ДАННЫХ:")
    
    try:
        async with KeitaroClient() as keitaro:
            
            # Точный запрос за тот же период что и CSV
            params = {
                "range": {
                    "from": "2025-08-05 00:00:00",
                    "to": "2025-08-05 23:59:59",
                    "timezone": "Europe/Moscow"
                }
            }
            
            data = await keitaro._make_request('/admin_api/v1/report/build', params, method="POST")
            rows = data.get('rows', [])
            
            print(f"   API Всего записей: {len(rows)}")
            
            # Фильтруем по n1
            n1_rows = [row for row in rows if row.get('sub_id_1') == 'n1']
            print(f"   API Записей n1: {len(n1_rows)}")
            
            # Анализ external_id в API
            api_external_ids = set()
            for row in n1_rows:
                ext_id = row.get('external_id')
                if ext_id and ext_id.strip():
                    api_external_ids.add(ext_id)
            
            print(f"   API Уникальные External ID: {len(api_external_ids)}")
            
            # Сравнение external_id
            common_ids = csv_external_ids & api_external_ids
            csv_only_ids = csv_external_ids - api_external_ids
            api_only_ids = api_external_ids - csv_external_ids
            
            print(f"\n🔍 СРАВНЕНИЕ EXTERNAL_ID:")
            print(f"   Общие ID: {len(common_ids)}")
            print(f"   Только в CSV: {len(csv_only_ids)}")
            print(f"   Только в API: {len(api_only_ids)}")
            
            if len(csv_only_ids) > 0:
                print(f"   Примеры ID только в CSV:")
                for ext_id in list(csv_only_ids)[:5]:
                    print(f"     {ext_id}")
            
            if len(api_only_ids) > 0:
                print(f"   Примеры ID только в API:")
                for ext_id in list(api_only_ids)[:5]:
                    print(f"     {ext_id}")
            
            # 3. Проверяем гипотезу о разных методах подсчета
            print(f"\n🧮 АНАЛИЗ МЕТОДОВ ПОДСЧЕТА:")
            
            # Метод 1: Суммирование полей leads/sales из API
            api_leads_sum = sum(int(row.get('leads', 0)) for row in n1_rows)
            api_sales_sum = sum(int(row.get('sales', 0)) for row in n1_rows)
            
            print(f"   API Метод 1 (суммирование полей):")
            print(f"     Лиды: {api_leads_sum}")
            print(f"     Продажи: {api_sales_sum}")
            
            # Метод 2: Подсчет записей с leads > 0
            api_leads_count = len([row for row in n1_rows if int(row.get('leads', 0)) > 0])
            api_sales_count = len([row for row in n1_rows if int(row.get('sales', 0)) > 0])
            
            print(f"   API Метод 2 (подсчет записей с leads > 0):")
            print(f"     Записей с лидами: {api_leads_count}")
            print(f"     Записей с продажами: {api_sales_count}")
            
            # Метод 3: Подсчет по external_id с конверсиями
            api_external_with_leads = set()
            api_external_with_sales = set()
            
            for row in n1_rows:
                ext_id = row.get('external_id')
                if ext_id and int(row.get('leads', 0)) > 0:
                    api_external_with_leads.add(ext_id)
                if ext_id and int(row.get('sales', 0)) > 0:
                    api_external_with_sales.add(ext_id)
            
            print(f"   API Метод 3 (уникальные external_id с конверсиями):")
            print(f"     External ID с лидами: {len(api_external_with_leads)}")
            print(f"     External ID с продажами: {len(api_external_with_sales)}")
            
            # 4. Проверяем совпадение с CSV
            print(f"\n📊 СРАВНЕНИЕ С CSV ЭТАЛОНОМ:")
            
            methods = [
                ("Суммирование полей", api_leads_sum, api_sales_sum),
                ("Подсчет записей", api_leads_count, api_sales_count),
                ("Уникальные External ID", len(api_external_with_leads), len(api_external_with_sales))
            ]
            
            print(f"{'Метод':<25} | {'Лиды':<8} | {'Продажи':<8} | {'Лиды ✓':<8} | {'Продажи ✓'}")
            print(f"{'-'*25} | {'-'*8} | {'-'*8} | {'-'*8} | {'-'*9}")
            print(f"{'CSV эталон':<25} | {csv_leads:<8} | {csv_sales:<8} | {'✓':<8} | {'✓'}")
            print(f"{'-'*25} | {'-'*8} | {'-'*8} | {'-'*8} | {'-'*9}")
            
            best_leads_method = None
            best_sales_method = None
            
            for method_name, api_leads, api_sales in methods:
                leads_match = api_leads == csv_leads
                sales_match = api_sales == csv_sales
                
                if leads_match:
                    best_leads_method = method_name
                if sales_match:
                    best_sales_method = method_name
                
                print(f"{method_name:<25} | {api_leads:<8} | {api_sales:<8} | {'✅' if leads_match else '❌':<8} | {'✅' if sales_match else '❌'}")
            
            # 5. Дополнительный анализ расхождений
            print(f"\n🔍 ДОПОЛНИТЕЛЬНЫЙ АНАЛИЗ РАСХОЖДЕНИЙ:")
            
            # Проверим, есть ли записи в API с конверсиями, но без external_id
            no_ext_id_but_has_conv = [
                row for row in n1_rows 
                if (not row.get('external_id') or not row.get('external_id').strip()) 
                and (int(row.get('leads', 0)) > 0 or int(row.get('sales', 0)) > 0)
            ]
            
            if no_ext_id_but_has_conv:
                print(f"   Записи без external_id, но с конверсиями: {len(no_ext_id_but_has_conv)}")
                leads_without_ext_id = sum(int(row.get('leads', 0)) for row in no_ext_id_but_has_conv)
                sales_without_ext_id = sum(int(row.get('sales', 0)) for row in no_ext_id_but_has_conv)
                print(f"     Лиды без external_id: {leads_without_ext_id}")
                print(f"     Продажи без external_id: {sales_without_ext_id}")
            
            # Проверим временное распределение конверсий в API
            api_conv_times = []
            for row in n1_rows:
                if int(row.get('conversions', 0)) > 0 and row.get('datetime'):
                    api_conv_times.append(row['datetime'])
            
            if api_conv_times:
                api_min_conv_time = min(api_conv_times)
                api_max_conv_time = max(api_conv_times)
                print(f"   API конверсии время от: {api_min_conv_time}")
                print(f"   API конверсии время до: {api_max_conv_time}")
            
            # 6. Итоговые выводы
            print(f"\n📋 ИТОГОВЫЕ ВЫВОДЫ:")
            
            if best_leads_method and best_sales_method:
                print(f"   ✅ Найден правильный метод подсчета:")
                print(f"     Лиды: {best_leads_method}")
                print(f"     Продажи: {best_sales_method}")
            elif best_leads_method or best_sales_method:
                print(f"   ⚠️ Частичное совпадение:")
                if best_leads_method:
                    print(f"     Лиды совпадают при методе: {best_leads_method}")
                if best_sales_method:
                    print(f"     Продажи совпадают при методе: {best_sales_method}")
            else:
                print(f"   ❌ Ни один метод не дает точного совпадения")
                print(f"   🔍 Возможные причины:")
                print(f"     - Разные источники данных (API vs Database)")
                print(f"     - Задержка в обновлении API")
                print(f"     - Разная логика подсчета конверсий")
                print(f"     - Фильтрация на уровне API")
            
            # Рекомендации
            print(f"\n🔧 РЕКОМЕНДАЦИИ:")
            
            if len(csv_only_ids) > len(api_only_ids):
                print(f"   📝 В CSV больше external_id чем в API")
                print(f"   💡 Возможно API не возвращает все конверсии")
                print(f"   🛠 Рекомендация: проверить фильтры API запроса")
            
            elif len(api_only_ids) > len(csv_only_ids):
                print(f"   📝 В API больше external_id чем в CSV")
                print(f"   💡 Возможно в API есть дополнительные данные")
                print(f"   🛠 Рекомендация: проверить период экспорта CSV")
            
            print(f"   📊 Текущая точность API:")
            accuracy_leads = (min(api_leads_sum, csv_leads) / max(api_leads_sum, csv_leads)) * 100
            accuracy_sales = (min(api_sales_sum, csv_sales) / max(api_sales_sum, csv_sales)) * 100 if csv_sales > 0 else 100
            print(f"     Лиды: {accuracy_leads:.1f}%")
            print(f"     Продажи: {accuracy_sales:.1f}%")

    except Exception as e:
        print(f"❌ Ошибка API: {e}")

async def main():
    """Главная функция"""
    
    await deep_comparison_api_vs_csv()

if __name__ == "__main__":
    asyncio.run(main())