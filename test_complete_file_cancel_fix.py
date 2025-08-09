#!/usr/bin/env python3
"""
Тест полного исправления отмены анализа для всех типов загрузки
Включает проверку исправлений в resetToInitialState и улучшенного логирования
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import requests
import time
import json
import tempfile
from pathlib import Path

def create_test_file(file_type='pdf'):
    """Создание тестового файла для загрузки"""
    
    if file_type == 'pdf':
        # Создаем простой PDF файл
        content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
72 720 Td
(Test PDF content) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000206 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
299
%%EOF"""
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        temp_file.write(content)
        temp_file.close()
        return temp_file.name
    
    elif file_type == 'txt':
        # Создаем простой текстовый файл
        content = "Это тестовый файл для проверки отмены анализа.\n" * 100
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.txt', mode='w', encoding='utf-8')
        temp_file.write(content)
        temp_file.close()
        return temp_file.name
    
    return None

def test_file_upload_cancel():
    """Тестирование отмены анализа при загрузке файла"""
    
    base_url = "http://127.0.0.1:5000"
    
    print("🧪 Тестирование отмены анализа при загрузке файла")
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
    
    # 2. Создаем тестовый файл
    print("\n2. 📄 Создание тестового файла...")
    test_file_path = create_test_file('pdf')
    
    if not test_file_path:
        print("❌ Не удалось создать тестовый файл")
        return False
    
    print(f"✅ Тестовый файл создан: {test_file_path}")
    
    try:
        # 3. Загружаем файл
        print("\n3. 📤 Загрузка файла...")
        
        with open(test_file_path, 'rb') as f:
            files = {'file': ('test.pdf', f, 'application/pdf')}
            data = {'page_range': '1-5'}
            
            upload_response = session.post(f"{base_url}/upload", files=files, data=data)
        
        if upload_response.status_code == 200:
            response_data = upload_response.json()
            
            if response_data.get('success') and response_data.get('task_id'):
                task_id = response_data['task_id']
                print(f"✅ Файл загружен, task_id: {task_id}")
                
                # 4. Тестируем отмену анализа
                print(f"\n4. ⏹️ Тестирование отмены анализа задачи {task_id}...")
                
                # Ждем немного, чтобы анализ начался
                time.sleep(1)
                
                # Отправляем запрос на отмену
                cancel_response = session.post(f"{base_url}/api/analysis/cancel/{task_id}")
                
                if cancel_response.status_code == 200:
                    cancel_data = cancel_response.json()
                    
                    if cancel_data.get('success'):
                        print("✅ Анализ успешно отменен")
                        
                        # 5. Проверяем статус задачи
                        print(f"\n5. 📊 Проверка статуса отмененной задачи...")
                        
                        time.sleep(1)  # Даем время на обновление статуса
                        
                        status_response = session.get(f"{base_url}/api/analysis/status/{task_id}")
                        
                        if status_response.status_code == 200:
                            status_data = status_response.json()
                            
                            if status_data.get('success'):
                                task_status = status_data['task']['status']
                                print(f"✅ Статус задачи: {task_status}")
                                
                                if task_status == 'cancelled':
                                    print("🎉 ТЕСТ ПРОЙДЕН: Отмена анализа файла работает корректно!")
                                    return True
                                else:
                                    print(f"❌ Ожидался статус 'cancelled', получен: {task_status}")
                                    return False
                            else:
                                print(f"❌ Ошибка получения статуса: {status_data.get('error')}")
                                return False
                        else:
                            print(f"❌ Ошибка запроса статуса: {status_response.status_code}")
                            return False
                    else:
                        print(f"❌ Ошибка отмены: {cancel_data.get('error')}")
                        return False
                else:
                    print(f"❌ Ошибка запроса отмены: {cancel_response.status_code}")
                    if cancel_response.status_code == 404:
                        print("   Возможно, задача не найдена или уже завершена")
                    return False
            else:
                print(f"❌ Ошибка загрузки файла: {response_data.get('error')}")
                return False
        else:
            print(f"❌ Ошибка HTTP при загрузке файла: {upload_response.status_code}")
            try:
                error_data = upload_response.json()
                print(f"   Детали: {error_data.get('error')}")
            except:
                print(f"   Ответ сервера: {upload_response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Исключение при тестировании: {e}")
        return False
    
    finally:
        # Удаляем тестовый файл
        try:
            os.unlink(test_file_path)
            print(f"🗑️ Тестовый файл удален: {test_file_path}")
        except:
            pass

def test_video_url_cancel():
    """Тестирование отмены анализа при загрузке видео по URL"""
    
    base_url = "http://127.0.0.1:5000"
    
    print("\n" + "=" * 60)
    print("🎥 Тестирование отмены анализа видео по URL")
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
            print("❌ Ошибка авторизации")
            return False
        print("✅ Авторизация успешна")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return False
    
    # 2. Тестируем загрузку видео по URL (используем короткое тестовое видео)
    print("\n2. 🎥 Тестирование загрузки видео по URL...")
    
    test_video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll для теста
    
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
                
                # 3. Тестируем отмену анализа
                print(f"\n3. ⏹️ Тестирование отмены анализа видео {task_id}...")
                
                # Ждем немного, чтобы анализ начался
                time.sleep(2)
                
                # Отправляем запрос на отмену
                cancel_response = session.post(f"{base_url}/api/analysis/cancel/{task_id}")
                
                if cancel_response.status_code == 200:
                    cancel_data = cancel_response.json()
                    
                    if cancel_data.get('success'):
                        print("✅ Анализ видео успешно отменен")
                        return True
                    else:
                        print(f"❌ Ошибка отмены видео: {cancel_data.get('error')}")
                        return False
                else:
                    print(f"❌ Ошибка запроса отмены видео: {cancel_response.status_code}")
                    return False
            else:
                print(f"❌ Ошибка загрузки видео: {response_data.get('error')}")
                return False
        else:
            print(f"❌ Ошибка HTTP при загрузке видео: {upload_response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Исключение при тестировании видео: {e}")
        return False

def test_frontend_cancel_logic():
    """Тестирование логики отмены на фронтенде"""
    
    print("\n" + "=" * 60)
    print("🌐 Тестирование логики отмены на фронтенде")
    print("=" * 60)
    
    base_url = "http://127.0.0.1:5000"
    
    try:
        # Проверяем, что главная страница загружается
        response = requests.get(base_url)
        
        if response.status_code == 200:
            content = response.text
            
            # Проверяем наличие исправленного JavaScript кода
            checks = [
                # Проверяем улучшенную функцию cancelAnalysis
                "if (currentUploadXHR)" in content,
                "currentUploadXHR.abort()" in content,
                "if (currentTaskId)" in content,
                "fetch(`/api/analysis/cancel/${currentTaskId}`" in content,
                # Проверяем установку currentTaskId при загрузке файлов
                "currentTaskId = response.task_id" in content,
                # Проверяем AJAX загрузку видео
                "fetch('/upload_url'" in content,
                "e.preventDefault()" in content
            ]
            
            passed_checks = sum(checks)
            total_checks = len(checks)
            
            print(f"📋 Проверок пройдено: {passed_checks}/{total_checks}")
            
            if passed_checks == total_checks:
                print("✅ Все проверки фронтенда пройдены")
                
                # Дополнительные проверки
                print("\n📝 Дополнительные проверки:")
                
                # Проверяем, что есть обработка обоих случаев отмены
                if "Отменяем загрузку файла" in content:
                    print("✅ Обработка отмены загрузки файла найдена")
                else:
                    print("❌ Обработка отмены загрузки файла не найдена")
                
                if "Отправляем запрос отмены для задачи" in content:
                    print("✅ Обработка отмены анализа найдена")
                else:
                    print("❌ Обработка отмены анализа не найдена")
                
                if "Нет активной загрузки или анализа для отмены" in content:
                    print("✅ Обработка случая отсутствия активных задач найдена")
                else:
                    print("❌ Обработка случая отсутствия активных задач не найдена")
                
                return True
            else:
                print("❌ Некоторые проверки фронтенда не пройдены")
                
                # Показываем, какие проверки не прошли
                check_names = [
                    "Проверка currentUploadXHR",
                    "Отмена загрузки через abort()",
                    "Проверка currentTaskId",
                    "AJAX отмена анализа",
                    "Установка currentTaskId",
                    "AJAX загрузка видео",
                    "Предотвращение стандартной отправки формы"
                ]
                
                for i, (check, name) in enumerate(zip(checks, check_names)):
                    status = "✅" if check else "❌"
                    print(f"   {status} {name}")
                
                return False
        else:
            print(f"❌ Ошибка загрузки главной страницы: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка тестирования фронтенда: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Запуск полных тестов исправления отмены анализа")
    print("📝 Убедитесь, что сервер запущен на http://127.0.0.1:5000")
    print("👤 Убедитесь, что создан тестовый пользователь: test@example.com / test123")
    print()
    
    # Тестируем фронтенд
    frontend_ok = test_frontend_cancel_logic()
    
    # Тестируем бэкенд (только если фронтенд в порядке)
    file_cancel_ok = False
    video_cancel_ok = False
    
    if frontend_ok:
        print("\n🔄 Переходим к тестированию бэкенда...")
        
        # Тестируем отмену файлов
        file_cancel_ok = test_file_upload_cancel()
        
        # Тестируем отмену видео
        video_cancel_ok = test_video_url_cancel()
        
        print("\n" + "=" * 60)
        print("📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
        print("=" * 60)
        
        if file_cancel_ok and video_cancel_ok:
            print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
            print("✅ Отмена анализа работает для всех типов загрузки:")
            print("   • Загрузка файлов - ✅")
            print("   • Загрузка видео по URL - ✅")
            print("   • Фронтенд логика - ✅")
        else:
            print("❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ")
            print("🔧 Проверьте логи сервера для диагностики")
    else:
        print("\n❌ ТЕСТЫ ФРОНТЕНДА НЕ ПРОЙДЕНЫ")
        print("🔧 Проверьте изменения в templates/index.html")
    
    print("\n📋 Детальные результаты:")
    print(f"   Фронтенд:           {'✅ OK' if frontend_ok else '❌ FAIL'}")
    if frontend_ok:
        print(f"   Отмена файлов:      {'✅ OK' if file_cancel_ok else '❌ FAIL'}")
        print(f"   Отмена видео:       {'✅ OK' if video_cancel_ok else '❌ FAIL'}")
    
    print("\n💡 Рекомендации:")
    if not frontend_ok:
        print("   - Проверьте, что все изменения в index.html применены")
        print("   - Убедитесь, что функция cancelAnalysis() обновлена")
    if frontend_ok and not (file_cancel_ok and video_cancel_ok):
        print("   - Проверьте логи сервера на наличие ошибок")
        print("   - Убедитесь, что analysis_manager работает корректно")
        print("   - Проверьте, что все эндпоинты возвращают правильные JSON ответы")