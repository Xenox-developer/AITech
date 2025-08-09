#!/usr/bin/env python3
"""
Тест исправления отмены транскрипции видео
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import requests
import time
import json
import threading

def test_video_transcription_cancel():
    """Тестирование отмены транскрипции видео"""
    
    base_url = "http://127.0.0.1:5000"
    
    print("🧪 Тестирование отмены транскрипции видео")
    print("=" * 60)
    
    # Создаем сессию для сохранения cookies
    session = requests.Session()
    
    # 1. Логинимся
    print("1. 🔐 Авторизация...")
    login_data = {
        'username': 'test@example.com',
        'password': 'test123'
    }
    
    try:
        login_response = session.post(f"{base_url}/login", data=login_data)
        if login_response.status_code != 200:
            print("❌ Ошибка авторизации. Создайте тестового пользователя.")
            return False
        print("✅ Авторизация успешна")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return False
    
    # 2. Тестируем загрузку видео по URL
    print("\n2. 🎥 Загрузка видео для тестирования отмены...")
    
    # Используем короткое тестовое видео, но достаточно длинное для отмены
    test_video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll
    
    video_data = {
        'video_url': test_video_url
    }
    
    try:
        # Отправляем запрос на загрузку видео
        upload_response = session.post(f"{base_url}/upload_url", data=video_data)
        
        if upload_response.status_code == 200:
            response_data = upload_response.json()
            
            if response_data.get('success') and response_data.get('task_id'):
                task_id = response_data['task_id']
                print(f"✅ Видео загружено, task_id: {task_id}")
                
                # 3. Ждем немного, чтобы транскрипция началась
                print(f"\n3. ⏳ Ждем начала транскрипции (5 секунд)...")
                time.sleep(5)
                
                # 4. Проверяем статус задачи
                print(f"\n4. 📊 Проверяем статус задачи...")
                status_response = session.get(f"{base_url}/api/analysis/status/{task_id}")
                
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    if status_data.get('success'):
                        task_status = status_data['task']['status']
                        current_stage = status_data['task'].get('current_stage', 'Unknown')
                        progress = status_data['task'].get('progress', 0)
                        
                        print(f"📋 Статус: {task_status}")
                        print(f"📋 Этап: {current_stage}")
                        print(f"📋 Прогресс: {progress}%")
                        
                        if task_status == 'processing':
                            print("✅ Задача в процессе выполнения, можно тестировать отмену")
                            
                            # 5. Отменяем задачу
                            print(f"\n5. ⏹️ Отменяем задачу {task_id}...")
                            cancel_response = session.post(f"{base_url}/api/analysis/cancel/{task_id}")
                            
                            if cancel_response.status_code == 200:
                                cancel_data = cancel_response.json()
                                
                                if cancel_data.get('success'):
                                    print("✅ Запрос на отмену отправлен успешно")
                                    
                                    # 6. Проверяем, что задача действительно отменена
                                    print(f"\n6. 🔍 Проверяем отмену через 3 секунды...")
                                    time.sleep(3)
                                    
                                    final_status_response = session.get(f"{base_url}/api/analysis/status/{task_id}")
                                    
                                    if final_status_response.status_code == 200:
                                        final_status_data = final_status_response.json()
                                        
                                        if final_status_data.get('success'):
                                            final_task_status = final_status_data['task']['status']
                                            print(f"📋 Финальный статус: {final_task_status}")
                                            
                                            if final_task_status == 'cancelled':
                                                print("🎉 ТЕСТ ПРОЙДЕН: Транскрипция видео успешно отменена!")
                                                return True
                                            else:
                                                print(f"❌ ТЕСТ НЕ ПРОЙДЕН: Ожидался статус 'cancelled', получен '{final_task_status}'")
                                                print("   Возможно, транскрипция завершилась до отмены")
                                                
                                                # Дополнительная проверка - ждем еще немного
                                                print("   Ждем еще 5 секунд для окончательной проверки...")
                                                time.sleep(5)
                                                
                                                extra_check_response = session.get(f"{base_url}/api/analysis/status/{task_id}")
                                                if extra_check_response.status_code == 200:
                                                    extra_check_data = extra_check_response.json()
                                                    if extra_check_data.get('success'):
                                                        extra_status = extra_check_data['task']['status']
                                                        print(f"   Дополнительная проверка: {extra_status}")
                                                        
                                                        if extra_status == 'cancelled':
                                                            print("🎉 ТЕСТ ПРОЙДЕН: Отмена сработала с задержкой!")
                                                            return True
                                                
                                                return False
                                        else:
                                            print(f"❌ Ошибка получения финального статуса: {final_status_data.get('error')}")
                                            return False
                                    else:
                                        print(f"❌ Ошибка запроса финального статуса: {final_status_response.status_code}")
                                        return False
                                else:
                                    print(f"❌ Ошибка отмены: {cancel_data.get('error')}")
                                    return False
                            else:
                                print(f"❌ Ошибка запроса отмены: {cancel_response.status_code}")
                                return False
                        else:
                            print(f"⚠️ Задача не в процессе выполнения (статус: {task_status})")
                            print("   Возможно, обработка завершилась слишком быстро для тестирования отмены")
                            return False
                    else:
                        print(f"❌ Ошибка получения статуса: {status_data.get('error')}")
                        return False
                else:
                    print(f"❌ Ошибка запроса статуса: {status_response.status_code}")
                    return False
            else:
                print(f"❌ Ошибка загрузки видео: {response_data.get('error')}")
                return False
        else:
            print(f"❌ Ошибка HTTP при загрузке видео: {upload_response.status_code}")
            try:
                error_data = upload_response.json()
                print(f"   Детали: {error_data.get('error')}")
            except:
                print(f"   Ответ сервера: {upload_response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Исключение при тестировании: {e}")
        return False

def test_multiple_cancellations():
    """Тестирование множественных отмен для проверки стабильности"""
    
    print("\n" + "=" * 60)
    print("🔄 Тестирование множественных отмен")
    print("=" * 60)
    
    success_count = 0
    total_tests = 3
    
    for i in range(total_tests):
        print(f"\n🧪 Тест {i+1}/{total_tests}")
        if test_video_transcription_cancel():
            success_count += 1
            print(f"✅ Тест {i+1} пройден")
        else:
            print(f"❌ Тест {i+1} не пройден")
        
        if i < total_tests - 1:
            print("⏳ Ждем 10 секунд перед следующим тестом...")
            time.sleep(10)
    
    print(f"\n📊 Результаты множественного тестирования:")
    print(f"   Успешных тестов: {success_count}/{total_tests}")
    print(f"   Процент успеха: {(success_count/total_tests)*100:.1f}%")
    
    return success_count == total_tests

if __name__ == "__main__":
    print("🚀 Запуск тестов отмены транскрипции видео")
    print("📝 Убедитесь, что сервер запущен на http://127.0.0.1:5000")
    print("👤 Убедитесь, что создан тестовый пользователь: test@example.com / test123")
    print("🎥 Убедитесь, что у вас есть доступ к YouTube для загрузки тестового видео")
    print()
    
    # Одиночный тест
    single_test_result = test_video_transcription_cancel()
    
    if single_test_result:
        print("\n🎯 Одиночный тест пройден! Запускаем множественное тестирование...")
        multiple_test_result = test_multiple_cancellations()
        
        if multiple_test_result:
            print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
            print("✅ Отмена транскрипции видео работает стабильно")
        else:
            print("\n⚠️ МНОЖЕСТВЕННЫЕ ТЕСТЫ ЧАСТИЧНО НЕ ПРОЙДЕНЫ")
            print("🔧 Возможны проблемы со стабильностью отмены")
    else:
        print("\n❌ ОДИНОЧНЫЙ ТЕСТ НЕ ПРОЙДЕН")
        print("🔧 Проверьте исправления в ml.py и analysis_manager.py")
    
    print("\n📋 Рекомендации для диагностики:")
    print("   - Проверьте логи сервера на наличие сообщений об отмене")
    print("   - Убедитесь, что функция transcribe_video_with_timestamps вызывает check_cancellation()")
    print("   - Проверьте, что analysis_manager.is_task_cancelled() работает корректно")
    print("   - Убедитесь, что задачи корректно помечаются как отмененные в БД")