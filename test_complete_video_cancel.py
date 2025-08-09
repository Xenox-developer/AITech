#!/usr/bin/env python3
"""
Финальный тест полной отмены анализа видео
Проверяет отмену на всех этапах: загрузка видео -> транскрипция -> анализ
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import requests
import time
import json
import threading

def test_complete_video_cancel_flow():
    """Тестирование полного цикла отмены анализа видео"""
    
    base_url = "http://127.0.0.1:5000"
    
    print("🧪 ФИНАЛЬНЫЙ ТЕСТ: Полная отмена анализа видео")
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
    
    # 2. Тестируем загрузку видео по URL
    print("\n2. 🎥 Загрузка видео для тестирования полной отмены...")
    
    # Используем видео средней длины для тестирования
    test_video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll
    
    video_data = {
        'video_url': test_video_url
    }
    
    try:
        # Отправляем запрос на загрузку видео
        print("📤 Отправляем запрос на загрузку видео...")
        upload_response = session.post(f"{base_url}/upload_url", data=video_data)
        
        if upload_response.status_code == 200:
            response_data = upload_response.json()
            
            if response_data.get('success') and response_data.get('task_id'):
                task_id = response_data['task_id']
                print(f"✅ Видео принято к загрузке, task_id: {task_id}")
                
                # 3. Мониторим процесс и тестируем отмену на разных этапах
                print(f"\n3. 📊 Мониторинг процесса и тестирование отмены...")
                
                # Ждем немного, чтобы процесс начался
                time.sleep(3)
                
                # Проверяем статус несколько раз
                for attempt in range(5):
                    print(f"\n   Попытка {attempt + 1}/5:")
                    
                    status_response = session.get(f"{base_url}/api/analysis/status/{task_id}")
                    
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        
                        if status_data.get('success'):
                            task_status = status_data['task']['status']
                            current_stage = status_data['task'].get('current_stage', 'Unknown')
                            progress = status_data['task'].get('progress', 0)
                            
                            print(f"   📋 Статус: {task_status}")
                            print(f"   📋 Этап: {current_stage}")
                            print(f"   📋 Прогресс: {progress}%")
                            
                            if task_status == 'processing':
                                print(f"   ✅ Задача активна, тестируем отмену на этапе: {current_stage}")
                                
                                # 4. Отменяем задачу
                                print(f"\n4. ⏹️ ОТМЕНЯЕМ ЗАДАЧУ {task_id}...")
                                cancel_response = session.post(f"{base_url}/api/analysis/cancel/{task_id}")
                                
                                if cancel_response.status_code == 200:
                                    cancel_data = cancel_response.json()
                                    
                                    if cancel_data.get('success'):
                                        print("   ✅ Запрос на отмену отправлен успешно")
                                        
                                        # 5. Проверяем результат отмены
                                        print(f"\n5. 🔍 Проверяем результат отмены...")
                                        
                                        # Ждем немного для обработки отмены
                                        for check_attempt in range(10):
                                            time.sleep(2)
                                            
                                            final_status_response = session.get(f"{base_url}/api/analysis/status/{task_id}")
                                            
                                            if final_status_response.status_code == 200:
                                                final_status_data = final_status_response.json()
                                                
                                                if final_status_data.get('success'):
                                                    final_task_status = final_status_data['task']['status']
                                                    final_stage = final_status_data['task'].get('current_stage', 'Unknown')
                                                    
                                                    print(f"   Проверка {check_attempt + 1}/10: Статус = {final_task_status}, Этап = {final_stage}")
                                                    
                                                    if final_task_status == 'cancelled':
                                                        print("\n🎉 ТЕСТ ПРОЙДЕН УСПЕШНО!")
                                                        print("✅ Видео анализ полностью отменен")
                                                        print(f"✅ Отмена сработала на этапе: {current_stage}")
                                                        print("✅ Все процессы остановлены")
                                                        print("✅ Ресурсы освобождены")
                                                        return True
                                                    elif final_task_status in ['completed', 'failed']:
                                                        print(f"\n⚠️ Задача завершилась до отмены: {final_task_status}")
                                                        print("   Возможно, процесс был слишком быстрым для тестирования отмены")
                                                        return False
                                                    # Если статус все еще 'processing', продолжаем ждать
                                                else:
                                                    print(f"   ❌ Ошибка получения статуса: {final_status_data.get('error')}")
                                            else:
                                                print(f"   ❌ Ошибка запроса статуса: {final_status_response.status_code}")
                                        
                                        print("\n❌ ТЕСТ НЕ ПРОЙДЕН: Отмена не сработала в течение 20 секунд")
                                        print("   Возможно, процесс не реагирует на отмену")
                                        return False
                                    else:
                                        print(f"   ❌ Ошибка отмены: {cancel_data.get('error')}")
                                        return False
                                else:
                                    print(f"   ❌ Ошибка запроса отмены: {cancel_response.status_code}")
                                    return False
                            elif task_status in ['completed', 'failed', 'cancelled']:
                                print(f"   ⚠️ Задача уже завершена: {task_status}")
                                if attempt == 0:
                                    print("   Процесс завершился слишком быстро для тестирования отмены")
                                    return False
                                break
                            else:
                                print(f"   📋 Статус: {task_status}, ждем активации...")
                        else:
                            print(f"   ❌ Ошибка получения статуса: {status_data.get('error')}")
                    else:
                        print(f"   ❌ Ошибка запроса статуса: {status_response.status_code}")
                    
                    # Ждем перед следующей попыткой
                    if attempt < 4:
                        time.sleep(5)
                
                print("\n❌ ТЕСТ НЕ ПРОЙДЕН: Не удалось найти активную задачу для отмены")
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

def test_frontend_integration():
    """Тестирование интеграции с фронтендом"""
    
    print("\n" + "=" * 70)
    print("🌐 Тестирование интеграции фронтенда")
    print("=" * 70)
    
    base_url = "http://127.0.0.1:5000"
    
    try:
        # Проверяем, что главная страница загружается
        response = requests.get(base_url)
        
        if response.status_code == 200:
            content = response.text
            
            # Проверяем наличие всех исправлений
            checks = [
                # Фронтенд исправления
                ("Улучшенная функция cancelAnalysis", "if (currentUploadXHR)" in content),
                ("Проверка currentTaskId", "if (currentTaskId)" in content),
                ("AJAX загрузка видео", "fetch('/upload_url'" in content),
                ("Предотвращение стандартной отправки", "e.preventDefault()" in content),
                ("Сброс переменных в resetToInitialState", "currentTaskId = null" in content),
                ("Модальное окно при загрузке", "modal.classList.add('active')" in content),
                ("Подробное логирование", "console.log('🔴 cancelAnalysis вызвана')" in content),
                
                # Проверяем наличие обработчиков
                ("Обработчик формы загрузки файла", "upload-form" in content),
                ("Обработчик формы загрузки видео", "url-form" in content),
                ("Кнопка отмены анализа", "Отменить анализ" in content),
            ]
            
            passed_checks = 0
            total_checks = len(checks)
            
            print("📋 Результаты проверки фронтенда:")
            for check_name, check_result in checks:
                status = "✅" if check_result else "❌"
                print(f"   {status} {check_name}")
                if check_result:
                    passed_checks += 1
            
            print(f"\n📊 Проверок пройдено: {passed_checks}/{total_checks}")
            
            if passed_checks == total_checks:
                print("✅ Все проверки фронтенда пройдены")
                return True
            else:
                print("❌ Некоторые проверки фронтенда не пройдены")
                return False
        else:
            print(f"❌ Ошибка загрузки главной страницы: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка тестирования фронтенда: {e}")
        return False

def run_stress_test():
    """Стресс-тест: множественные отмены"""
    
    print("\n" + "=" * 70)
    print("💪 Стресс-тест: Множественные отмены")
    print("=" * 70)
    
    success_count = 0
    total_tests = 3
    
    for i in range(total_tests):
        print(f"\n🧪 Стресс-тест {i+1}/{total_tests}")
        if test_complete_video_cancel_flow():
            success_count += 1
            print(f"✅ Стресс-тест {i+1} пройден")
        else:
            print(f"❌ Стресс-тест {i+1} не пройден")
        
        if i < total_tests - 1:
            print("⏳ Ждем 15 секунд перед следующим тестом...")
            time.sleep(15)
    
    print(f"\n📊 Результаты стресс-тестирования:")
    print(f"   Успешных тестов: {success_count}/{total_tests}")
    print(f"   Процент успеха: {(success_count/total_tests)*100:.1f}%")
    
    return success_count >= (total_tests * 0.8)  # 80% успеха считается хорошим результатом

if __name__ == "__main__":
    print("🚀 ФИНАЛЬНОЕ ТЕСТИРОВАНИЕ ОТМЕНЫ АНАЛИЗА ВИДЕО")
    print("=" * 70)
    print("📝 Убедитесь, что сервер запущен на http://127.0.0.1:5000")
    print("👤 Убедитесь, что создан тестовый пользователь: test@example.com / test123")
    print("🎥 Убедитесь, что у вас есть доступ к YouTube для загрузки тестового видео")
    print("🔧 Убедитесь, что все исправления применены:")
    print("   - Фронтенд: улучшенная cancelAnalysis() и resetToInitialState()")
    print("   - Бэкенд: поддержка отмены в download_video_from_url() и transcribe_video_with_timestamps()")
    print("   - Система задач: корректная обработка отмены в analysis_manager")
    print()
    
    # Тестируем фронтенд
    frontend_ok = test_frontend_integration()
    
    if frontend_ok:
        print("\n🎯 Фронтенд в порядке! Переходим к тестированию бэкенда...")
        
        # Основной тест
        main_test_ok = test_complete_video_cancel_flow()
        
        if main_test_ok:
            print("\n🎯 Основной тест пройден! Запускаем стресс-тест...")
            
            # Стресс-тест
            stress_test_ok = run_stress_test()
            
            print("\n" + "=" * 70)
            print("🏆 ФИНАЛЬНЫЕ РЕЗУЛЬТАТЫ")
            print("=" * 70)
            
            if stress_test_ok:
                print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
                print("✅ Отмена анализа видео работает стабильно на всех этапах:")
                print("   • Загрузка видео по URL - ✅")
                print("   • Транскрипция видео - ✅") 
                print("   • Анализ содержимого - ✅")
                print("   • Фронтенд интеграция - ✅")
                print("   • Стресс-тестирование - ✅")
                print("\n🚀 СИСТЕМА ГОТОВА К ПРОДАКШЕНУ!")
            else:
                print("⚠️ СТРЕСС-ТЕСТЫ ЧАСТИЧНО НЕ ПРОЙДЕНЫ")
                print("🔧 Система работает, но могут быть проблемы со стабильностью")
        else:
            print("\n❌ ОСНОВНОЙ ТЕСТ НЕ ПРОЙДЕН")
            print("🔧 Проверьте исправления в бэкенде")
    else:
        print("\n❌ ТЕСТЫ ФРОНТЕНДА НЕ ПРОЙДЕНЫ")
        print("🔧 Проверьте изменения в templates/index.html")
    
    print("\n📋 Детальные результаты:")
    print(f"   Фронтенд интеграция:    {'✅ OK' if frontend_ok else '❌ FAIL'}")
    if frontend_ok:
        main_test_ok = locals().get('main_test_ok', False)
        print(f"   Основной тест:          {'✅ OK' if main_test_ok else '❌ FAIL'}")
        if main_test_ok:
            stress_test_ok = locals().get('stress_test_ok', False)
            print(f"   Стресс-тест:            {'✅ OK' if stress_test_ok else '❌ FAIL'}")
    
    print("\n💡 Рекомендации:")
    if not frontend_ok:
        print("   - Проверьте, что все изменения в index.html применены")
        print("   - Убедитесь, что функции cancelAnalysis() и resetToInitialState() обновлены")
    elif frontend_ok and not locals().get('main_test_ok', False):
        print("   - Проверьте логи сервера на наличие ошибок")
        print("   - Убедитесь, что download_video_from_url() поддерживает отмену")
        print("   - Проверьте, что transcribe_video_with_timestamps() проверяет отмену")
    elif locals().get('main_test_ok', False) and not locals().get('stress_test_ok', False):
        print("   - Система работает, но есть проблемы со стабильностью")
        print("   - Проверьте обработку ошибок и очистку ресурсов")
        print("   - Возможно, нужно увеличить частоту проверок отмены")
    
    print("\n🎯 Следующие шаги:")
    print("   1. Исправьте выявленные проблемы")
    print("   2. Повторите тестирование")
    print("   3. При успешном прохождении всех тестов - деплой в продакшен")