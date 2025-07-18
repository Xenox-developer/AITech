#!/usr/bin/env python3
"""
Расширенный тестовый скрипт для диагностики проблем с обработкой видео
"""

import os
import sys
import tempfile
import logging
from pathlib import Path

# Настройка логирования для диагностики
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_imports():
    """Тест импорта всех необходимых библиотек"""
    print("📦 Проверяем импорты...")
    
    try:
        import yt_dlp
        print("✅ yt-dlp установлен")
    except ImportError:
        print("❌ yt-dlp не установлен. Установите: pip install yt-dlp")
        return False
    
    try:
        import whisperx
        print("✅ whisperx установлен")
    except ImportError:
        print("❌ whisperx не установлен. Установите: pip install whisperx")
        return False
    
    try:
        import torch
        print(f"✅ torch установлен (CUDA: {'доступна' if torch.cuda.is_available() else 'недоступна'})")
    except ImportError:
        print("❌ torch не установлен")
        return False
    
    try:
        from app import download_video_from_url, is_valid_video_url
        print("✅ Функции приложения импортированы")
    except ImportError as e:
        print(f"❌ Ошибка импорта функций приложения: {e}")
        return False
    
    return True

def test_whisper_models():
    """Тест загрузки моделей Whisper"""
    print("\n🤖 Проверяем модели Whisper...")
    
    try:
        from ml import load_models, whisper_model
        
        if whisper_model is None:
            print("⚠️  Модель Whisper не загружена, пытаемся загрузить...")
            load_models()
        
        if whisper_model is not None:
            print("✅ Модель Whisper загружена успешно")
            return True
        else:
            print("❌ Не удалось загрузить модель Whisper")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при работе с моделями Whisper: {e}")
        return False

def test_url_validation():
    """Тест валидации URL"""
    print("\n🔍 Тестируем валидацию URL...")
    
    from app import is_valid_video_url
    
    valid_urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://vimeo.com/123456789",
        "https://rutube.ru/video/123456/",
        "https://ok.ru/video/123456",
        "https://vk.com/video123456_789"
    ]
    
    invalid_urls = [
        "https://example.com/video.mp4",
        "https://google.com",
        "not-a-url",
        ""
    ]
    
    print("✅ Валидные URL:")
    for url in valid_urls:
        result = is_valid_video_url(url)
        print(f"  {url} -> {'✓' if result else '✗'}")
    
    print("\n❌ Невалидные URL:")
    for url in invalid_urls:
        result = is_valid_video_url(url)
        print(f"  {url} -> {'✓' if result else '✗'}")

def test_video_download():
    """Тест загрузки видео"""
    print("\n📥 Тестируем загрузку видео...")
    
    from app import download_video_from_url
    
    # Используем короткое тестовое видео
    test_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # "Me at the zoo" - 11 секунд
    
    try:
        # Используем uploads директорию вместо временной
        temp_dir = "uploads"
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
            
        print(f"Загружаем: {test_url}")
        filepath, filename, title = download_video_from_url(test_url, temp_dir)
        
        print(f"✅ Успешно загружено:")
        print(f"  Файл: {filename}")
        print(f"  Название: {title}")
        print(f"  Размер: {os.path.getsize(filepath) / (1024*1024):.2f} МБ")
        
        if os.path.exists(filepath):
            print("✅ Файл существует и доступен")
            return filepath, filename
        else:
            print("❌ Файл не найден")
            return None, None
                
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        return None, None

def test_video_transcription(filepath, filename):
    """Тест транскрипции видео"""
    print(f"\n🎤 Тестируем транскрипцию видео: {filename}")
    
    try:
        from ml import transcribe_video_with_timestamps, transcribe_video_simple
        
        print("Пытаемся выполнить полную транскрипцию с временными метками...")
        result = transcribe_video_with_timestamps(filepath)
        
        if result and result.get('full_text'):
            print(f"✅ Полная транскрипция успешна:")
            print(f"  Текст: {len(result['full_text'])} символов")
            print(f"  Сегменты: {len(result.get('segments', []))}")
            print(f"  Ключевые моменты: {len(result.get('key_moments', []))}")
            print(f"  Язык: {result.get('language', 'неизвестен')}")
            print(f"  Длительность: {result.get('total_duration', 0):.2f} сек")
            
            # Показываем первые 200 символов текста
            if result['full_text']:
                preview = result['full_text'][:200] + "..." if len(result['full_text']) > 200 else result['full_text']
                print(f"  Превью текста: {preview}")
            
            return True
        else:
            print("❌ Полная транскрипция не дала результата")
            
            print("Пытаемся простую транскрипцию...")
            simple_text = transcribe_video_simple(filepath)
            
            if simple_text:
                print(f"✅ Простая транскрипция успешна: {len(simple_text)} символов")
                preview = simple_text[:200] + "..." if len(simple_text) > 200 else simple_text
                print(f"  Превью: {preview}")
                return True
            else:
                print("❌ Простая транскрипция также не дала результата")
                return False
                
    except Exception as e:
        print(f"❌ Ошибка транскрипции: {e}")
        logger.exception("Подробности ошибки транскрипции:")
        return False

def test_full_processing(filepath, filename):
    """Тест полной обработки файла"""
    print(f"\n🧠 Тестируем полную обработку файла: {filename}")
    
    try:
        from ml import process_file
        
        result = process_file(filepath, filename)
        
        if result:
            print("✅ Полная обработка успешна:")
            print(f"  Темы: {len(result.get('topics_data', {}).get('main_topics', []))}")
            print(f"  Флеш-карты: {len(result.get('flashcards', []))}")
            print(f"  Резюме: {len(result.get('summary', ''))} символов")
            print(f"  Видео сегменты: {len(result.get('video_segments', []))}")
            print(f"  Ключевые моменты: {len(result.get('key_moments', []))}")
            
            # Показываем первую тему
            topics = result.get('topics_data', {}).get('main_topics', [])
            if topics:
                first_topic = topics[0]
                print(f"  Первая тема: {first_topic.get('title', 'Без названия')}")
            
            return True
        else:
            print("❌ Полная обработка не дала результата")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка полной обработки: {e}")
        logger.exception("Подробности ошибки полной обработки:")
        return False

def main():
    print("🎥 Расширенная диагностика обработки видео\n")
    
    # Проверяем импорты
    if not test_imports():
        print("\n❌ Критические ошибки импорта. Исправьте их перед продолжением.")
        return
    
    # Проверяем модели
    if not test_whisper_models():
        print("\n⚠️  Проблемы с моделями Whisper. Это может быть причиной проблем.")
    
    # Тестируем валидацию URL
    test_url_validation()
    
    # Спрашиваем о тесте загрузки
    response = input("\n🤔 Хотите протестировать загрузку и обработку видео? (y/N): ").strip().lower()
    if response not in ['y', 'yes', 'да']:
        print("⏭️  Пропускаем тест обработки видео")
        return
    
    # Тестируем загрузку
    filepath, filename = test_video_download()
    if not filepath:
        print("\n❌ Не удалось загрузить видео для тестирования")
        return
    
    try:
        # Тестируем транскрипцию
        transcription_success = test_video_transcription(filepath, filename)
        
        if transcription_success:
            # Тестируем полную обработку
            processing_success = test_full_processing(filepath, filename)
            
            if processing_success:
                print("\n🎉 Все тесты прошли успешно!")
            else:
                print("\n⚠️  Транскрипция работает, но есть проблемы с полной обработкой")
        else:
            print("\n❌ Проблема в транскрипции видео - это основная причина")
            
    finally:
        # Очищаем временный файл
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"🗑️  Временный файл {filename} удален")
    
    print("\n✅ Диагностика завершена!")

if __name__ == "__main__":
    main()