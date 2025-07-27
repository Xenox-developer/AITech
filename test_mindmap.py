#!/usr/bin/env python3
"""
Тест для проверки mind-map данных в базе
"""

import sqlite3
import json
import sys

def test_mindmap_data():
    """Проверяем mind-map данные в базе"""
    try:
        conn = sqlite3.connect('ai_study.db')
        c = conn.cursor()
        
        # Получаем последние результаты
        c.execute('''
            SELECT id, filename, mind_map_json 
            FROM result 
            ORDER BY created_at DESC 
            LIMIT 5
        ''')
        
        results = c.fetchall()
        
        if not results:
            print("❌ Нет результатов в базе данных")
            return False
        
        print(f"📊 Найдено {len(results)} результатов:")
        
        for result_id, filename, mind_map_json in results:
            print(f"\n🔍 ID: {result_id}, Файл: {filename}")
            
            if not mind_map_json:
                print("  ❌ mind_map_json пустой")
                continue
            
            try:
                mind_map_data = json.loads(mind_map_json)
                print(f"  ✅ mind_map_json загружен")
                
                # Проверяем структуру
                if 'central_topic' in mind_map_data:
                    print(f"  📍 Центральная тема: {mind_map_data['central_topic']}")
                else:
                    print("  ❌ Нет central_topic")
                
                if 'branches' in mind_map_data:
                    branches = mind_map_data['branches']
                    print(f"  🌿 Веток: {len(branches)}")
                    
                    for i, branch in enumerate(branches[:3]):  # Показываем первые 3
                        name = branch.get('name', 'Без названия')
                        children_count = len(branch.get('children', []))
                        print(f"    {i+1}. {name} ({children_count} подтем)")
                else:
                    print("  ❌ Нет branches")
                    
            except json.JSONDecodeError as e:
                print(f"  ❌ Ошибка парсинга JSON: {e}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def test_api_endpoint():
    """Тестируем API endpoint"""
    try:
        import requests
        
        # Получаем ID последнего результата
        conn = sqlite3.connect('ai_study.db')
        c = conn.cursor()
        c.execute('SELECT id FROM result ORDER BY created_at DESC LIMIT 1')
        result = c.fetchone()
        conn.close()
        
        if not result:
            print("❌ Нет результатов для тестирования API")
            return False
        
        result_id = result[0]
        url = f'http://localhost:5000/api/mind_map/{result_id}'
        
        print(f"🌐 Тестируем API: {url}")
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ API работает")
            print(f"📊 Данные: {json.dumps(data, ensure_ascii=False, indent=2)}")
            return True
        else:
            print(f"❌ API ошибка: {response.status_code}")
            print(f"📄 Ответ: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка тестирования API: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Тестирование Mind-Map данных\n")
    
    print("1️⃣ Проверка данных в базе:")
    db_ok = test_mindmap_data()
    
    print("\n2️⃣ Проверка API endpoint:")
    api_ok = test_api_endpoint()
    
    print(f"\n📋 Результат:")
    print(f"  База данных: {'✅' if db_ok else '❌'}")
    print(f"  API endpoint: {'✅' if api_ok else '❌'}")
    
    if not db_ok or not api_ok:
        print("\n🔧 Возможные проблемы:")
        if not db_ok:
            print("  - Mind-map данные не генерируются или не сохраняются")
            print("  - Проблема с функцией generate_mind_map")
        if not api_ok:
            print("  - API endpoint не работает")
            print("  - Сервер не запущен")
            print("  - Проблема с маршрутом /api/mind_map")