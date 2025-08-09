#!/usr/bin/env python3
"""
Тест автоматического удаления видеофайлов после обработки и отмены
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import requests
import time
import json
import tempfile
from pathlib import Path

def test_video_cleanup_after_completion():
    """Тестирование удаления видеофайлов после успешного завершения анализа"""
    
    base_url = "http://127.0.0.1:5000"
    
    print("🧪 Тестирование удаления видеофайлов после завершения анализа")
    print("=" * 70)
    
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
    
    # 2. Проверяем состояние папки uploads до загрузки
    print("\n2. 📁 Проверяем состояние папки uploads...")
    upload_folder = "uploads"
    
    if os.path.exists(upload_folder):
        files_before = set(os.listdir(upload_folder))
        print(f"   Файлов в папке до загрузки: {len(files_before)}")
    else:
        files_before = set()
        print("   Папка uploads не существует")
    
    # 3. Загружаем короткое видео для быстрого тестирования
    print("\n3. 🎥 Загружаем короткое видео...")
    
    # Используем короткое видео для быстрого завершения
    test_video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll (короткое)
    
    video_data = {
        'video_url': test_video_url
    }
    
    try:
        upload_response = session.post(f"{base_url}/upload_url", data=video_data)
        
        if upload_response.status_code == 200:
            response_data = upload_response.json()
            
            if response_data.get('success') and response_data.get('task_id'):
                task_id = response_data['task_id']
                print(f"✅ Видео принято к обработке, task_id: {task_id}")
                
                # 4. Проверяем, что файл появился в папке uploads
                print("\n4. 📁 Проверяем появление файла в uploads...")
                
                # Ждем немного для загрузки
                time.sleep(10)
                
                if os.path.exists(upload_folder):
                    files_during = set(os.listdir(upload_folder))
                    new_files = files_during - files_before
                    
                    if new_files:
                        print(f"✅ Новые файлы появились: {list(new_files)}")
                        video_file = list(new_files)[0]  # Берем первый новый файл
                        video_path = os.path.join(upload_folder, video_file)
                        
                        if os.path.exists(video_path):
                            file_size = os.path.getsize(video_path)
                            print(f"   Размер видеофайла: {file_size} bytes")
                        else:
                            print("❌ Видеофайл не найден")
                            return False
                    else:
                        print("⚠️ Новые файлы не обнаружены (возможно, загрузка еще идет)")
                
                # 5. Ждем завершения анализа
                print("\n5. ⏳ Ждем завершения анализа...")
                
                max_wait_time = 300  # 5 минут максимум
                start_time = time.time()
                
                while time.time() - start_time < max_wait_time:
                    status_response = session.get(f"{base_url}/api/analysis/status/{task_id}")
                    
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        
                        if status_data.get('success'):
                            task_status = status_data['task']['status']
                            current_stage = status_data['task'].get('current_stage', 'Unknown')
                            progress = status_data['task'].get('progress', 0)
                            
                            print(f"   📊 Статус: {task_status}, Этап: {current_stage}, Прогресс: {progress}%")
                            
                            if task_status == 'completed':
                                print("✅ Анализ завершен успешно!")
                                break
                            elif task_status in ['failed', 'cancelled']:
                                print(f"❌ Анализ завершился со статусом: {task_status}")
                                return False
                        else:
                            print(f"❌ Ошибка получения статуса: {status_data.get('error')}")
                            return False
                    else:
                        print(f"❌ Ошибка запроса статуса: {status_response.status_code}")
                        return False
                    
                    time.sleep(10)  # Проверяем каждые 10 секунд
                else:
                    print("❌ Превышено время ожидания завершения анализа")
                    return False
                
                # 6. Проверяем, что видеофайл удален после завершения
                print("\n6. 🗑️ Проверяем удаление видеофайла...")
                
                # Ждем немного для завершения очистки
                time.sleep(5)
                
                if os.path.exists(upload_folder):
                    files_after = set(os.listdir(upload_folder))
                    remaining_new_files = files_after - files_before
                    
                    if not remaining_new_files:
                        print("✅ Видеофайл успешно удален после завершения анализа!")
                        return True
                    else:
                        print(f"❌ Видеофайл не удален: {list(remaining_new_files)}")
                        
                        # Дополнительная информация для диагностики
                        for file in remaining_new_files:
                            file_path = os.path.join(upload_folder, file)
                            if os.path.exists(file_path):
                                file_size = os.path.getsize(file_path)
                                file_age = time.time() - os.path.getmtime(file_path)
                                print(f"   Файл: {file}, Размер: {file_size} bytes, Возраст: {file_age:.1f} сек")
                        
                        return False
                else:
                    print("⚠️ Папка uploads исчезла")
                    return True  # Это тоже считается успешной очисткой
                
            else:
                print(f"❌ Ошибка загрузки видео: {response_data.get('error')}")
                return False
        else:
            print(f"❌ Ошибка HTTP при загрузке видео: {upload_response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Исключение при тестировании: {e}")
        return False

def test_video_cleanup_after_cancellation():
    """Тестирование удаления видеофайлов после отмены анализа"""
    
    base_url = "http://127.0.0.1:5000"
    
    print("\n" + "=" * 70)
    print("🧪 Тестирование удаления видеофайлов после отмены анализа")
    print("=" * 70)
    
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
            print("❌ Ошибка авторизации")
            return False
        print("✅ Авторизация успешна")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return False
    
    # 2. Проверяем состояние папки uploads до загрузки
    print("\n2. 📁 Проверяем состояние папки uploads...")
    upload_folder = "uploads"
    
    if os.path.exists(upload_folder):
        files_before = set(os.listdir(upload_folder))
        print(f"   Файлов в папке до загрузки: {len(files_before)}")
    else:
        files_before = set()
        print("   Папка uploads не существует")
    
    # 3. Загружаем видео
    print("\n3. 🎥 Загружаем видео для тестирования отмены...")
    
    test_video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    video_data = {
        'video_url': test_video_url
    }
    
    try:
        upload_response = session.post(f"{base_url}/upload_url", data=video_data)
        
        if upload_response.status_code == 200:
            response_data = upload_response.json()
            
            if response_data.get('success') and response_data.get('task_id'):
                task_id = response_data['task_id']
                print(f"✅ Видео принято к обработке, task_id: {task_id}")
                
                # 4. Ждем начала обработки
                print("\n4. ⏳ Ждем начала обработки...")
                time.sleep(5)
                
                # 5. Отменяем анализ
                print(f"\n5. ⏹️ Отменяем анализ задачи {task_id}...")
                
                cancel_response = session.post(f"{base_url}/api/analysis/cancel/{task_id}")
                
                if cancel_response.status_code == 200:
                    cancel_data = cancel_response.json()
                    
                    if cancel_data.get('success'):
                        print("✅ Запрос на отмену отправлен успешно")
                        
                        # 6. Ждем обработки отмены
                        print("\n6. ⏳ Ждем обработки отмены...")
                        time.sleep(10)
                        
                        # 7. Проверяем, что видеофайл удален после отмены
                        print("\n7. 🗑️ Проверяем удаление видеофайла после отмены...")
                        
                        if os.path.exists(upload_folder):
                            files_after = set(os.listdir(upload_folder))
                            remaining_new_files = files_after - files_before
                            
                            if not remaining_new_files:
                                print("✅ Видеофайл успешно удален после отмены анализа!")
                                return True
                            else:
                                print(f"❌ Видеофайл не удален после отмены: {list(remaining_new_files)}")
                                
                                # Дополнительная информация
                                for file in remaining_new_files:
                                    file_path = os.path.join(upload_folder, file)
                                    if os.path.exists(file_path):
                                        file_size = os.path.getsize(file_path)
                                        file_age = time.time() - os.path.getmtime(file_path)
                                        print(f"   Файл: {file}, Размер: {file_size} bytes, Возраст: {file_age:.1f} сек")
                                
                                return False
                        else:
                            print("⚠️ Папка uploads исчезла")
                            return True
                    else:
                        print(f"❌ Ошибка отмены: {cancel_data.get('error')}")
                        return False
                else:
                    print(f"❌ Ошибка запроса отмены: {cancel_response.status_code}")
                    return False
            else:
                print(f"❌ Ошибка загрузки видео: {response_data.get('error')}")
                return False
        else:
            print(f"❌ Ошибка HTTP при загрузке видео: {upload_response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Исключение при тестировании: {e}")
        return False

def test_cleanup_api():
    """Тестирование API очистки файлов"""
    
    base_url = "http://127.0.0.1:5000"
    
    print("\n" + "=" * 70)
    print("🧪 Тестирование API очистки файлов")
    print("=" * 70)
    
    # Создаем сессию для сохранения cookies
    session = requests.Session()
    
    # 1. Логинимся как администратор
    print("1. 🔐 Авторизация как администратор...")
    login_data = {
        'username': 'test@test.ru',  # Администратор
        'password': 'admin123'
    }
    
    try:
        login_response = session.post(f"{base_url}/login", data=login_data)
        if login_response.status_code != 200:
            print("❌ Ошибка авторизации администратора")
            print("   Создайте пользователя test@test.ru с паролем admin123")
            return False
        print("✅ Авторизация администратора успешна")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return False
    
    # 2. Тестируем получение статистики очистки
    print("\n2. 📊 Получаем статистику файлов...")
    
    try:
        stats_response = session.get(f"{base_url}/api/cleanup/status")
        
        if stats_response.status_code == 200:
            stats_data = stats_response.json()
            
            if stats_data.get('success'):
                stats = stats_data['stats']
                print("✅ Статистика получена:")
                print(f"   Всего файлов: {stats['total_files']}")
                print(f"   Общий размер: {stats['total_size_mb']} MB")
                print(f"   Старых файлов: {stats['old_files']}")
                print(f"   Размер старых файлов: {stats['old_size_mb']} MB")
                print(f"   Активных файлов: {stats['active_files']}")
            else:
                print(f"❌ Ошибка получения статистики: {stats_data.get('error')}")
                return False
        else:
            print(f"❌ Ошибка HTTP при получении статистики: {stats_response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Исключение при получении статистики: {e}")
        return False
    
    # 3. Тестируем ручную очистку
    print("\n3. 🧹 Тестируем ручную очистку...")
    
    try:
        cleanup_data = {
            'upload_folder': 'uploads',
            'task_days': 7,
            'file_hours': 0  # Удаляем все файлы старше 0 часов для тестирования
        }
        
        cleanup_response = session.post(
            f"{base_url}/api/cleanup/files",
            json=cleanup_data,
            headers={'Content-Type': 'application/json'}
        )
        
        if cleanup_response.status_code == 200:
            cleanup_result = cleanup_response.json()
            
            if cleanup_result.get('success'):
                print("✅ Ручная очистка выполнена успешно")
                print(f"   Сообщение: {cleanup_result.get('message')}")
                return True
            else:
                print(f"❌ Ошибка ручной очистки: {cleanup_result.get('error')}")
                return False
        else:
            print(f"❌ Ошибка HTTP при ручной очистке: {cleanup_response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Исключение при ручной очистке: {e}")
        return False

if __name__ == "__main__":
    print("🚀 ТЕСТИРОВАНИЕ АВТОМАТИЧЕСКОГО УДАЛЕНИЯ ВИДЕОФАЙЛОВ")
    print("=" * 70)
    print("📝 Убедитесь, что сервер запущен на http://127.0.0.1:5000")
    print("👤 Убедитесь, что созданы тестовые пользователи:")
    print("   - test@example.com / test123 (обычный пользователь)")
    print("   - test@test.ru / admin123 (администратор)")
    print("🎥 Убедитесь, что у вас есть доступ к YouTube")
    print()
    
    # Тестируем удаление после завершения
    completion_test_ok = test_video_cleanup_after_completion()
    
    # Тестируем удаление после отмены
    cancellation_test_ok = test_video_cleanup_after_cancellation()
    
    # Тестируем API очистки
    api_test_ok = test_cleanup_api()
    
    print("\n" + "=" * 70)
    print("📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
    print("=" * 70)
    
    all_tests_passed = completion_test_ok and cancellation_test_ok and api_test_ok
    
    if all_tests_passed:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("✅ Автоматическое удаление видеофайлов работает корректно:")
        print("   • После успешного завершения анализа - ✅")
        print("   • После отмены анализа - ✅")
        print("   • API ручной очистки - ✅")
        print("\n🚀 СИСТЕМА ГОТОВА К ПРОДАКШЕНУ!")
    else:
        print("❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ")
        print("🔧 Проверьте логи сервера для диагностики")
    
    print("\n📋 Детальные результаты:")
    print(f"   Удаление после завершения:  {'✅ OK' if completion_test_ok else '❌ FAIL'}")
    print(f"   Удаление после отмены:      {'✅ OK' if cancellation_test_ok else '❌ FAIL'}")
    print(f"   API очистки:                {'✅ OK' if api_test_ok else '❌ FAIL'}")
    
    print("\n💡 Рекомендации:")
    if not completion_test_ok:
        print("   - Проверьте, что файлы удаляются в analysis_manager.py после завершения")
        print("   - Убедитесь, что логирование удаления работает корректно")
    if not cancellation_test_ok:
        print("   - Проверьте, что файлы удаляются при отмене в analysis_manager.py")
        print("   - Убедитесь, что очистка происходит в download_video_from_url при отмене")
    if not api_test_ok:
        print("   - Проверьте права администратора для пользователя test@test.ru")
        print("   - Убедитесь, что API эндпоинты /api/cleanup/* работают корректно")
    
    print("\n🎯 Следующие шаги:")
    if all_tests_passed:
        print("   1. Система готова к продакшену")
        print("   2. Автоматическая очистка будет работать каждые 6 часов")
        print("   3. Администраторы могут использовать API для ручной очистки")
    else:
        print("   1. Исправьте выявленные проблемы")
        print("   2. Повторите тестирование")
        print("   3. При успешном прохождении - деплой в продакшен")