# Руководство по автоматическому удалению видеофайлов

## 🎯 Проблема решена!

Теперь все видеофайлы автоматически удаляются из папки `uploads` после обработки или отмены, что экономит дисковое пространство и предотвращает накопление ненужных файлов.

## 🔧 Что было реализовано:

### 1. **Автоматическое удаление после успешного анализа**
```python
# В analysis_manager.py - start_video_analysis_task()
# ✅ УЛУЧШЕНО: Удаляем видеофайл после успешного анализа
if Path(filepath).exists():
    file_size = Path(filepath).stat().st_size
    Path(filepath).unlink()
    logger.info(f"🗑️ Video file deleted after successful analysis: {filename} ({file_size} bytes)")
```

### 2. **Автоматическое удаление при отмене анализа**
```python
# В analysis_manager.py - при отмене задачи
if self.is_task_cancelled(task_id):
    if Path(filepath).exists():
        file_size = Path(filepath).stat().st_size
        Path(filepath).unlink()
        logger.info(f"🗑️ Video file deleted after cancellation: {filename} ({file_size} bytes)")
```

### 3. **Автоматическое удаление при ошибках**
```python
# В analysis_manager.py - при ошибке обработки
except Exception as e:
    if Path(filepath).exists():
        file_size = Path(filepath).stat().st_size
        Path(filepath).unlink()
        logger.info(f"🗑️ Video file deleted after error: {filename} ({file_size} bytes)")
```

### 4. **Очистка при отмене загрузки**
```python
# В app.py - download_video_from_url()
except Exception as e:
    if "cancelled" in str(e).lower():
        # Удаляем все новые файлы, которые могли быть загружены
        for file in new_files:
            file_path = os.path.join(upload_folder, file)
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"🗑️ Removed cancelled download: {file}")
```

### 5. **Периодическая очистка осиротевших файлов**
```python
# В analysis_manager.py - cleanup_orphaned_files()
def cleanup_orphaned_files(self, upload_folder: str = "uploads", max_age_hours: int = 24):
    """Очистка осиротевших файлов в папке uploads"""
    # Удаляет файлы старше 24 часов, которые не связаны с активными задачами
```

### 6. **Автоматический планировщик очистки**
```python
# В app.py - запускается при старте сервера
def start_background_cleanup():
    """Запуск фоновой очистки файлов каждые 6 часов"""
    # Автоматически очищает старые файлы и задачи
```

## 🚀 Как это работает:

### **Жизненный цикл видеофайла:**

1. **📥 Загрузка видео**
   - Видео загружается в папку `uploads/`
   - Создается задача анализа в БД

2. **🎬 Обработка видео**
   - Транскрипция через Whisper
   - Анализ содержимого через GPT
   - Генерация результатов

3. **🗑️ Автоматическое удаление** (один из сценариев):
   - **✅ Успешное завершение** → файл удаляется после сохранения результата
   - **⏹️ Отмена пользователем** → файл удаляется немедленно
   - **❌ Ошибка обработки** → файл удаляется для очистки
   - **⏰ Старый файл** → удаляется планировщиком (>24 часов)

### **Планировщик очистки:**
- **Запуск**: Автоматически при старте сервера
- **Частота**: Каждые 6 часов
- **Что удаляет**:
  - Задачи старше 7 дней
  - Файлы старше 24 часов (не связанные с активными задачами)

## 🛠️ API для управления очисткой:

### **Получение статистики файлов:**
```bash
GET /api/cleanup/status
```
**Ответ:**
```json
{
  "success": true,
  "stats": {
    "total_files": 15,
    "total_size_mb": 245.7,
    "old_files": 3,
    "old_size_mb": 67.2,
    "active_files": 2
  }
}
```

### **Ручная очистка (только для администраторов):**
```bash
POST /api/cleanup/files
Content-Type: application/json

{
  "upload_folder": "uploads",
  "task_days": 7,
  "file_hours": 24
}
```

## 🧪 Тестирование:

### **Автоматические тесты:**
```bash
cd AITech

# Полный тест автоматического удаления
python test_video_cleanup.py
```

### **Ручное тестирование:**

1. **Тест удаления после завершения:**
   - Загрузите короткое видео
   - Дождитесь завершения анализа
   - Проверьте, что файл удален из `uploads/`

2. **Тест удаления после отмены:**
   - Загрузите видео
   - Отмените анализ
   - Проверьте, что файл удален из `uploads/`

3. **Тест планировщика:**
   - Создайте старый файл в `uploads/`
   - Подождите 6 часов или перезапустите сервер
   - Проверьте, что старый файл удален

## 🔍 Мониторинг и логирование:

### **Логи удаления файлов:**
```
🗑️ Video file deleted after successful analysis: video.mp4 (15728640 bytes)
🗑️ Video file deleted after cancellation: video.mp4 (8294400 bytes)
🗑️ Video file deleted after error: video.mp4 (12582912 bytes)
🗑️ Removed cancelled download: temp_video.mp4
```

### **Логи планировщика:**
```
🧹 Starting scheduled cleanup...
🗑️ Removed orphaned file: old_video.mp4 (25165824 bytes, 26.3h old)
✅ Cleanup completed: 3 files removed, 67.2 MB freed
✅ Scheduled cleanup completed
```

## 📊 Преимущества системы:

### **Экономия дискового пространства:**
- ✅ Видеофайлы удаляются сразу после обработки
- ✅ Нет накопления старых файлов
- ✅ Автоматическая очистка осиротевших файлов

### **Надежность:**
- ✅ Удаление во всех сценариях (успех, отмена, ошибка)
- ✅ Защита от удаления активных файлов
- ✅ Подробное логирование всех операций

### **Управляемость:**
- ✅ API для мониторинга и ручной очистки
- ✅ Настраиваемые параметры очистки
- ✅ Автоматический планировщик

## ⚙️ Настройки:

### **Параметры планировщика (в app.py):**
```python
# Частота очистки
time.sleep(6 * 60 * 60)  # 6 часов

# Параметры очистки
analysis_manager.cleanup_all(
    upload_folder='uploads',
    task_days=7,      # Удаляем задачи старше 7 дней
    file_hours=24     # Удаляем файлы старше 24 часов
)
```

### **Изменение настроек:**
Для изменения параметров очистки отредактируйте значения в функции `start_background_cleanup()` в файле `app.py`.

## 🎉 Результат:

**Система полностью автоматизирована!**

- ✅ **Видеофайлы никогда не накапливаются** в папке uploads
- ✅ **Дисковое пространство экономится** автоматически
- ✅ **Администраторы могут мониторить** использование через API
- ✅ **Система самоочищается** без вмешательства человека
- ✅ **Подробные логи** для диагностики и мониторинга

**Проблема решена на 100%!** 🎯

Теперь сервер может работать неограниченно долго без накопления видеофайлов и переполнения диска.