#!/usr/bin/env python3
"""
Тестовый скрипт для проверки улучшенной валидации файлов
"""

import os
import sys
import tempfile
from pathlib import Path

# Добавляем текущую директорию в путь для импорта модулей
sys.path.append(str(Path(__file__).parent))

from app import allowed_file, validate_file_content, _check_file_signature, _is_compatible_mime_type

def create_test_files():
    """Создает тестовые файлы с различными расширениями и содержимым"""
    test_files = []
    
    # Создаем временную директорию
    temp_dir = tempfile.mkdtemp()
    
    # 1. Правильный PDF файл (с PDF заголовком)
    pdf_file = os.path.join(temp_dir, "test.pdf")
    with open(pdf_file, 'wb') as f:
        f.write(b'%PDF-1.4\n%Test PDF content')
    test_files.append(("test.pdf", pdf_file, "PDF", True))
    
    # 2. Файл с расширением PDF, но без PDF заголовка
    fake_pdf = os.path.join(temp_dir, "fake.pdf")
    with open(fake_pdf, 'wb') as f:
        f.write(b'This is not a PDF file')
    test_files.append(("fake.pdf", fake_pdf, "Fake PDF", False))
    
    # 3. Правильный MP4 файл (с ftyp заголовком)
    mp4_file = os.path.join(temp_dir, "test.mp4")
    with open(mp4_file, 'wb') as f:
        f.write(b'\x00\x00\x00\x20ftypmp41\x00\x00\x00\x00mp41isom')
    test_files.append(("test.mp4", mp4_file, "MP4", True))
    
    # 4. Файл с расширением MP4, но неверным содержимым
    fake_mp4 = os.path.join(temp_dir, "fake.mp4")
    with open(fake_mp4, 'wb') as f:
        f.write(b'This is not an MP4 file')
    test_files.append(("fake.mp4", fake_mp4, "Fake MP4", False))
    
    # 5. MOV файл
    mov_file = os.path.join(temp_dir, "test.mov")
    with open(mov_file, 'wb') as f:
        f.write(b'\x00\x00\x00\x14ftypqt  ')
    test_files.append(("test.mov", mov_file, "MOV", True))
    
    # 6. MKV файл
    mkv_file = os.path.join(temp_dir, "test.mkv")
    with open(mkv_file, 'wb') as f:
        f.write(b'\x1a\x45\xdf\xa3\x93\x42\x82\x88matroska')
    test_files.append(("test.mkv", mkv_file, "MKV", True))
    
    # 7. Неподдерживаемый формат
    txt_file = os.path.join(temp_dir, "test.txt")
    with open(txt_file, 'w') as f:
        f.write("This is a text file")
    test_files.append(("test.txt", txt_file, "TXT", False))
    
    # 8. Файл без расширения
    no_ext_file = os.path.join(temp_dir, "noextension")
    with open(no_ext_file, 'wb') as f:
        f.write(b'%PDF-1.4\nPDF without extension')
    test_files.append(("noextension", no_ext_file, "No extension", False))
    
    return test_files, temp_dir

def test_allowed_file():
    """Тестирует функцию allowed_file"""
    print("🧪 ТЕСТИРОВАНИЕ ФУНКЦИИ allowed_file()")
    print("=" * 50)
    
    test_cases = [
        ("document.pdf", True),
        ("video.mp4", True),
        ("movie.mov", True),
        ("video.mkv", True),
        ("document.PDF", True),  # Заглавные буквы
        ("video.MP4", True),
        ("document.txt", False),
        ("image.jpg", False),
        ("archive.zip", False),
        ("", False),
        ("noextension", False),
        (".pdf", True),  # Только расширение
        ("file.", False),  # Точка без расширения
        ("file.pdf.txt", False),  # Двойное расширение
    ]
    
    passed = 0
    total = len(test_cases)
    
    for filename, expected in test_cases:
        result = allowed_file(filename)
        status = "✅" if result == expected else "❌"
        print(f"{status} {filename:<20} -> {result:<5} (ожидалось: {expected})")
        if result == expected:
            passed += 1
    
    print(f"\nРезультат: {passed}/{total} тестов пройдено ({passed/total*100:.1f}%)")
    return passed == total

def test_file_signature():
    """Тестирует функцию _check_file_signature"""
    print("\n🧪 ТЕСТИРОВАНИЕ ФУНКЦИИ _check_file_signature()")
    print("=" * 50)
    
    test_cases = [
        (b'%PDF-1.4\nContent', 'pdf', True, 'PDF'),
        (b'Not a PDF', 'pdf', False, None),
        (b'\x00\x00\x00\x20ftypmp41', 'mp4', True, 'MP4/MOV'),
        (b'Not a video', 'mp4', False, None),
        (b'\x1a\x45\xdf\xa3', 'mkv', True, 'MKV'),
        (b'Not MKV', 'mkv', False, None),
    ]
    
    passed = 0
    total = len(test_cases)
    
    for content, ext, expected_valid, expected_type in test_cases:
        is_valid, detected_type = _check_file_signature(content, ext)
        status = "✅" if (is_valid == expected_valid and detected_type == expected_type) else "❌"
        print(f"{status} {ext.upper():<4} signature -> valid: {is_valid}, type: {detected_type}")
        if is_valid == expected_valid and detected_type == expected_type:
            passed += 1
    
    print(f"\nРезультат: {passed}/{total} тестов пройдено ({passed/total*100:.1f}%)")
    return passed == total

def test_mime_compatibility():
    """Тестирует функцию _is_compatible_mime_type"""
    print("\n🧪 ТЕСТИРОВАНИЕ ФУНКЦИИ _is_compatible_mime_type()")
    print("=" * 50)
    
    test_cases = [
        ('application/pdf', 'pdf', True),
        ('application/x-pdf', 'pdf', True),
        ('text/pdf', 'pdf', True),
        ('video/mp4', 'mp4', True),
        ('video/x-mp4', 'mp4', True),
        ('video/quicktime', 'mov', True),
        ('video/x-matroska', 'mkv', True),
        ('text/plain', 'pdf', False),
        ('image/jpeg', 'mp4', False),
    ]
    
    passed = 0
    total = len(test_cases)
    
    for mime_type, ext, expected in test_cases:
        result = _is_compatible_mime_type(mime_type, ext)
        status = "✅" if result == expected else "❌"
        print(f"{status} {mime_type:<25} + {ext:<4} -> {result}")
        if result == expected:
            passed += 1
    
    print(f"\nРезультат: {passed}/{total} тестов пройдено ({passed/total*100:.1f}%)")
    return passed == total

def test_file_validation():
    """Тестирует полную валидацию файлов"""
    print("\n🧪 ТЕСТИРОВАНИЕ ПОЛНОЙ ВАЛИДАЦИИ ФАЙЛОВ")
    print("=" * 50)
    
    test_files, temp_dir = create_test_files()
    
    passed = 0
    total = len(test_files)
    
    for filename, filepath, description, should_be_valid in test_files:
        try:
            # Тест allowed_file
            extension_valid = allowed_file(filename)
            
            # Тест validate_file_content
            if extension_valid:
                with open(filepath, 'rb') as f:
                    class MockFile:
                        def __init__(self, file_obj):
                            self.file_obj = file_obj
                            self.content = file_obj.read()
                            file_obj.seek(0)
                        
                        def seek(self, pos):
                            self.file_obj.seek(pos)
                        
                        def read(self, size=-1):
                            return self.file_obj.read(size)
                    
                    mock_file = MockFile(f)
                    is_valid, warning = validate_file_content(mock_file, filename)
                    
                    overall_valid = extension_valid and is_valid
                    
                    status = "✅" if (overall_valid == should_be_valid or not should_be_valid) else "❌"
                    warning_text = f" (⚠️ {warning})" if warning else ""
                    
                    print(f"{status} {description:<15} ({filename:<12}) -> ext: {extension_valid}, content: {is_valid}{warning_text}")
                    
                    if overall_valid == should_be_valid or (not should_be_valid and not overall_valid):
                        passed += 1
            else:
                status = "✅" if not should_be_valid else "❌"
                print(f"{status} {description:<15} ({filename:<12}) -> расширение не поддерживается")
                if not should_be_valid:
                    passed += 1
                    
        except Exception as e:
            print(f"❌ {description:<15} ({filename:<12}) -> ОШИБКА: {str(e)}")
    
    # Очистка временных файлов
    import shutil
    shutil.rmtree(temp_dir)
    
    print(f"\nРезультат: {passed}/{total} тестов пройдено ({passed/total*100:.1f}%)")
    return passed == total

def main():
    """Основная функция тестирования"""
    print("🔍 ТЕСТИРОВАНИЕ УЛУЧШЕННОЙ ВАЛИДАЦИИ ФАЙЛОВ")
    print("=" * 60)
    
    results = []
    
    # Запуск всех тестов
    results.append(test_allowed_file())
    results.append(test_file_signature())
    results.append(test_mime_compatibility())
    results.append(test_file_validation())
    
    # Итоговый отчет
    print(f"\n{'='*60}")
    print("📊 ИТОГОВЫЙ ОТЧЕТ")
    print(f"{'='*60}")
    
    test_names = [
        "Проверка расширений",
        "Проверка сигнатур файлов", 
        "Совместимость MIME-типов",
        "Полная валидация файлов"
    ]
    
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"{name}: {status}")
    
    success_rate = sum(results) / len(results) * 100
    print(f"\nОбщий процент успеха: {success_rate:.1f}%")
    
    if all(results):
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Система валидации файлов работает корректно.")
        print("\n💡 Улучшения:")
        print("   • Проверка расширений файлов")
        print("   • Валидация содержимого по сигнатурам")
        print("   • Совместимость MIME-типов")
        print("   • Обработка ошибок и предупреждений")
        print("   • Поддержка альтернативных методов детекции")
    else:
        print("\n⚠️  Некоторые тесты провалены. Проверьте реализацию.")
    
    return all(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)