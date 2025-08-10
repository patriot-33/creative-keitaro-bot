#!/usr/bin/env python3
"""
Проверка гипотезы об агрегации данных в Keitaro API
КРИТИЧЕСКАЯ ВАЖНОСТЬ: reg2dep зависит от точного подсчета лидов
"""

import asyncio
import sys
from pathlib import Path
import pandas as pd
from collections import defaultdict, Counter

# Добавляем путь к проекту
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from integrations.keitaro.client import KeitaroClient

async def test_api_aggregation_hypothesis():
    """Проверяем гипотезу что API агрегирует данные неправильно"""
    
    print("🧪 ПРОВЕРКА ГИПОТЕЗЫ ОБ АГРЕГАЦИИ ДАННЫХ В API")
    print("=" * 70)
    
    # 1. Анализ CSV данных на дубликаты
    print("📊 АНАЛИЗ CSV НА ПРЕДМЕТ ДУБЛИКАТОВ:")
    
    try:
        conversions_df = pd.read_csv("n1 conversions 050825.csv", sep=";", encoding='utf-8')
        n1_conversions = conversions_df[conversions_df['Sub ID 1'] == 'n1']
        csv_leads = n1_conversions[n1_conversions['Статус'] == 'lead']
        
        print(f"   CSV всего лидов: {len(csv_leads)}")
        
        # Проверяем дубликаты по External ID
        external_ids = csv_leads['External ID'].values
        external_id_counts = Counter(external_ids)
        duplicates = {ext_id: count for ext_id, count in external_id_counts.items() if count > 1}
        
        print(f"   Уникальных External ID в CSV: {len(external_id_counts)}")
        print(f"   Дубликатов External ID в CSV: {len(duplicates)}")
        
        if duplicates:
            print(f"   Примеры дубликатов в CSV:")
            for ext_id, count in list(duplicates.items())[:3]:
                print(f"     {ext_id}: {count} раз")
                
                # Показать детали дубликатов
                dup_records = csv_leads[csv_leads['External ID'] == ext_id]
                for _, record in dup_records.iterrows():
                    print(f"       {record['Время конверсии']} | {record['Sub ID 2']}")
        
        # Подсчет уникальных лидов
        unique_csv_leads = len(external_id_counts)
        print(f"   💡 Если убрать дубликаты в CSV: {unique_csv_leads} лидов")
        
    except Exception as e:
        print(f"❌ Ошибка анализа CSV: {e}")
        return
    
    # 2. Детальный анализ API данных
    print(f"\n🌐 ДЕТАЛЬНЫЙ АНАЛИЗ API ДАННЫХ:")
    
    try:
        async with KeitaroClient() as keitaro:
            
            params = {
                "range": {
                    "from": "2025-08-05 00:00:00",
                    "to": "2025-08-05 23:59:59",
                    "timezone": "Europe/Moscow"
                }
            }
            
            data = await keitaro._make_request('/admin_api/v1/report/build', params, method="POST")
            rows = data.get('rows', [])
            n1_rows = [row for row in rows if row.get('sub_id_1') == 'n1']
            
            print(f"   API всего записей n1: {len(n1_rows)}")
            
            # Анализ записей с лидами
            lead_rows = [row for row in n1_rows if int(row.get('leads', 0)) > 0]
            print(f"   API записей с лидами: {len(lead_rows)}")
            
            # Группировка по external_id для анализа агрегации
            external_id_groups = defaultdict(list)
            for row in n1_rows:
                ext_id = row.get('external_id', '')
                if ext_id:
                    external_id_groups[ext_id].append(row)
            
            print(f"   API уникальных External ID: {len(external_id_groups)}")
            
            # Анализ дубликатов в API
            api_duplicates = {ext_id: rows for ext_id, rows in external_id_groups.items() if len(rows) > 1}
            print(f"   API дубликатов External ID: {len(api_duplicates)}")
            
            if api_duplicates:
                print(f"   Примеры дубликатов в API:")
                for ext_id, duplicate_rows in list(api_duplicates.items())[:3]:
                    print(f"     {ext_id}: {len(duplicate_rows)} записей")
                    
                    total_leads = sum(int(row.get('leads', 0)) for row in duplicate_rows)
                    total_clicks = sum(int(row.get('clicks', 0)) for row in duplicate_rows)
                    
                    print(f"       Суммарно лидов: {total_leads}")
                    print(f"       Суммарно кликов: {total_clicks}")
                    
                    for i, row in enumerate(duplicate_rows[:2]):  # Показать первые 2
                        print(f"       #{i+1}: {row.get('datetime')} | leads={row.get('leads')} | clicks={row.get('clicks')}")
            
            # 3. КРИТИЧЕСКАЯ ПРОВЕРКА: Как API обрабатывает дубликаты
            print(f"\n🔬 КРИТИЧЕСКАЯ ПРОВЕРКА ОБРАБОТКИ ДУБЛИКАТОВ:")
            
            # Метод 1: Просто суммируем все поля leads (текущий подход)
            api_leads_sum = sum(int(row.get('leads', 0)) for row in n1_rows)
            
            # Метод 2: Группируем по external_id и берем максимум leads на каждый ID
            api_leads_max_per_id = 0
            for ext_id, group_rows in external_id_groups.items():
                max_leads_for_id = max(int(row.get('leads', 0)) for row in group_rows)
                api_leads_max_per_id += max_leads_for_id
            
            # Метод 3: Группируем по external_id и суммируем leads для каждого ID
            api_leads_sum_per_id = 0
            for ext_id, group_rows in external_id_groups.items():
                sum_leads_for_id = sum(int(row.get('leads', 0)) for row in group_rows)
                api_leads_sum_per_id += sum_leads_for_id
            
            # Метод 4: Учитываем только записи с уникальным external_id + datetime
            unique_combinations = set()
            api_leads_unique_combo = 0
            
            for row in n1_rows:
                ext_id = row.get('external_id', '')
                datetime_val = row.get('datetime', '')
                combo_key = f"{ext_id}_{datetime_val}"
                
                if combo_key not in unique_combinations:
                    unique_combinations.add(combo_key)
                    api_leads_unique_combo += int(row.get('leads', 0))
            
            print(f"   Метод 1 (простое суммирование): {api_leads_sum} лидов")
            print(f"   Метод 2 (max по external_id): {api_leads_max_per_id} лидов")  
            print(f"   Метод 3 (сумма по external_id): {api_leads_sum_per_id} лидов")
            print(f"   Метод 4 (уникальные external_id+datetime): {api_leads_unique_combo} лидов")
            
            # Сравниваем с эталоном
            csv_target = 329  # Из нашего анализа
            
            print(f"\n🎯 СРАВНЕНИЕ С CSV ЭТАЛОНОМ ({csv_target} лидов):")
            
            methods = [
                ("Простое суммирование", api_leads_sum),
                ("Max по external_id", api_leads_max_per_id),
                ("Сумма по external_id", api_leads_sum_per_id), 
                ("Уникальные комбинации", api_leads_unique_combo)
            ]
            
            best_method = None
            best_diff = float('inf')
            
            for method_name, result in methods:
                diff = abs(result - csv_target)
                percentage = (result / csv_target) * 100
                
                if diff < best_diff:
                    best_diff = diff
                    best_method = method_name
                
                status = "✅" if diff == 0 else "⚠️" if diff < 10 else "❌"
                print(f"   {status} {method_name}: {result} ({percentage:.1f}% от эталона, разница: {diff})")
            
            print(f"\n🏆 ЛУЧШИЙ МЕТОД: {best_method} (отклонение: {best_diff})")
            
            # 4. Анализ конкретных отсутствующих external_id
            print(f"\n🔍 АНАЛИЗ КОНКРЕТНЫХ ОТСУТСТВУЮЩИХ EXTERNAL_ID:")
            
            # Загружаем отсутствующие ID из предыдущего анализа
            csv_all_ext_ids = set(conversions_df[conversions_df['Sub ID 1'] == 'n1']['External ID'].dropna().values)
            api_all_ext_ids = set(row.get('external_id', '') for row in n1_rows if row.get('external_id'))
            
            missing_in_api = csv_all_ext_ids - api_all_ext_ids
            print(f"   Отсутствуют в API: {len(missing_in_api)} external_id")
            
            # Проверим, есть ли эти ID в сыром API ответе (возможно с другими полями)
            print(f"   Проверяем присутствие в сыром API ответе...")
            
            found_with_different_fields = 0
            missing_examples = []
            
            for missing_id in list(missing_in_api)[:5]:  # Проверим первые 5
                # Ищем этот ID во всех записях API (не только n1)
                found_records = [row for row in rows if row.get('external_id') == missing_id]
                
                if found_records:
                    found_with_different_fields += 1
                    print(f"     ✅ {missing_id} найден в API:")
                    for record in found_records[:2]:  # Показать первые 2
                        print(f"       sub_id_1={record.get('sub_id_1')} | leads={record.get('leads')} | conversions={record.get('conversions')}")
                        missing_examples.append({
                            'external_id': missing_id,
                            'sub_id_1': record.get('sub_id_1'),
                            'leads': record.get('leads'),
                            'reason': 'different_sub_id_1' if record.get('sub_id_1') != 'n1' else 'no_leads'
                        })
                else:
                    print(f"     ❌ {missing_id} полностью отсутствует в API")
                    missing_examples.append({
                        'external_id': missing_id,
                        'reason': 'not_in_api_at_all'
                    })
            
            print(f"   Найдено с другими полями: {found_with_different_fields}/{len(list(missing_in_api)[:5])}")
            
            # 5. Итоговые выводы
            print(f"\n📋 ИТОГОВЫЕ ВЫВОДЫ:")
            
            if best_diff == 0:
                print(f"   🎯 ПРОБЛЕМА РЕШЕНА! Метод '{best_method}' дает точное совпадение")
                print(f"   🔧 РЕКОМЕНДАЦИЯ: Изменить логику подсчета в боте на этот метод")
            elif best_diff < 10:
                print(f"   ⚠️ ЗНАЧИТЕЛЬНОЕ УЛУЧШЕНИЕ: Метод '{best_method}' почти точен (отклонение: {best_diff})")
                print(f"   🔧 РЕКОМЕНДАЦИЯ: Рассмотреть использование этого метода")
            else:
                print(f"   ❌ АГРЕГАЦИЯ НЕ РЕШАЕТ ПРОБЛЕМУ")
                print(f"   💡 ВОЗМОЖНЫЕ ПРИЧИНЫ:")
                print(f"     - API не возвращает все данные")
                print(f"     - Разные источники: API vs Database")
                print(f"     - Фильтрация на уровне Keitaro")
                print(f"     - Временные рамки не совпадают точно")
            
            return {
                'best_method': best_method,
                'best_result': methods[[m[0] for m in methods].index(best_method)][1],
                'best_diff': best_diff,
                'csv_target': csv_target
            }

    except Exception as e:
        print(f"❌ Ошибка API: {e}")

async def suggest_keitaro_client_fix(analysis_result):
    """Предложить исправление в KeitaroClient на основе анализа"""
    
    if not analysis_result:
        return
    
    print(f"\n🔧 ПРЕДЛАГАЕМОЕ ИСПРАВЛЕНИЕ KEITAROCLIENT:")
    print("=" * 60)
    
    if analysis_result['best_diff'] == 0:
        print(f"🎯 Найден точный метод: {analysis_result['best_method']}")
        
        print(f"\n📝 КОД ДЛЯ ИСПРАВЛЕНИЯ:")
        print(f"В файле src/integrations/keitaro/client.py")
        print(f"В методе get_stats_by_buyers(), заменить логику подсчета лидов:")
        
        if analysis_result['best_method'] == 'Max по external_id':
            print(f"""
# ВМЕСТО:
stats['leads'] += int(row.get('leads', 0))

# ИСПОЛЬЗОВАТЬ:
# Группировка по external_id и взятие максимума
external_id_groups = defaultdict(list)
for row in rows:
    ext_id = row.get('external_id', '')
    if ext_id:
        external_id_groups[ext_id].append(row)

for buyer, stats in buyer_stats.items():
    leads_total = 0
    for ext_id, group_rows in external_id_groups.items():
        # Фильтруем по этому buyer
        buyer_rows = [r for r in group_rows if r.get('sub_id_1') == buyer]
        if buyer_rows:
            max_leads = max(int(r.get('leads', 0)) for r in buyer_rows)
            leads_total += max_leads
    stats['leads'] = leads_total
""")
        
        elif analysis_result['best_method'] == 'Уникальные комбинации':
            print(f"""
# ВМЕСТО:
stats['leads'] += int(row.get('leads', 0))

# ИСПОЛЬЗОВАТЬ:
# Дедупликация по external_id + datetime
unique_combinations = set()
for row in rows:
    buyer = row.get('sub_id_1', '')
    if buyer in buyer_stats:
        ext_id = row.get('external_id', '')
        datetime_val = row.get('datetime', '')
        combo_key = f"{{ext_id}}_{{datetime_val}}"
        
        if combo_key not in unique_combinations:
            unique_combinations.add(combo_key)
            buyer_stats[buyer]['leads'] += int(row.get('leads', 0))
""")
        
        print(f"\n✅ ОЖИДАЕМЫЙ РЕЗУЛЬТАТ: {analysis_result['best_result']} лидов вместо 283")
        print(f"✅ ТОЧНОСТЬ reg2dep: 100%")
        
    elif analysis_result['best_diff'] < 10:
        print(f"⚠️ Частичное улучшение возможно: {analysis_result['best_method']}")
        print(f"📊 Улучшение с 283 до {analysis_result['best_result']} лидов")
        print(f"📈 Точность reg2dep: {(analysis_result['best_result']/analysis_result['csv_target']*100):.1f}%")
        
    else:
        print(f"❌ Агрегация не решает основную проблему")
        print(f"🔍 Нужны дальнейшие исследования источника данных")

async def main():
    """Главная функция"""
    
    print("💎 КРИТИЧЕСКАЯ ЗАДАЧА: Найти точный метод подсчета лидов для reg2dep")
    
    result = await test_api_aggregation_hypothesis()
    await suggest_keitaro_client_fix(result)
    
    print(f"\n🎯 ЗАКЛЮЧЕНИЕ:")
    print(f"reg2dep показатель критически важен для бизнеса")
    print(f"Без точного подсчета лидов этот показатель будет некорректным")
    print(f"Необходимо найти способ получить все 329 лидов через API")

if __name__ == "__main__":
    asyncio.run(main())