# 🚀 Руководство по развертыванию AITech

## Быстрое развертывание

### 1. Первоначальная настройка
```bash
# Клонирование репозитория
git clone <repository-url>
cd AITech

# Автоматическая настройка
./setup.sh
```

### 2. Настройка переменных окружения
```bash
# Создайте .env файл на основе примера
cp env_example.txt .env

# Обязательно добавьте:
OPENAI_API_KEY=your_openai_api_key_here
SECRET_KEY=your_secret_key_here
```

### 3. Запуск приложения
```bash
# Активация виртуального окружения
source venv/bin/activate

# Запуск приложения
python app.py
```

## 🗄️ Система миграций

### Как это работает
- Миграции автоматически применяются при запуске `setup.sh`
- Миграции также запускаются при инициализации приложения
- Все миграции отслеживаются в таблице `migrations`

### Создание новой миграции
1. Создайте файл в папке `migrations/` с именем `XXX_description.py`
2. Реализуйте функции `up(conn)` и `down(conn)`
3. Миграция будет автоматически применена при следующем запуске

Пример миграции:
```python
"""
Migration 002: Add new column example
"""
import sqlite3
import logging

logger = logging.getLogger(__name__)

def up(conn):
    """Apply migration"""
    c = conn.cursor()
    try:
        c.execute('ALTER TABLE users ADD COLUMN new_field TEXT DEFAULT NULL')
        logger.info("Added new_field column to users table")
    except sqlite3.OperationalError as e:
        logger.warning(f"Column might already exist: {e}")

def down(conn):
    """Rollback migration"""
    # SQLite doesn't support DROP COLUMN easily
    logger.warning("Rollback not implemented for this migration")
    pass
```

### Команды миграций
```bash
# Проверить статус
python migration_manager.py status

# Применить все ожидающие миграции
python migration_manager.py migrate

# Применить конкретную миграцию (программно)
python -c "from migration_manager import MigrationManager; MigrationManager().apply_migration('001_add_user_columns')"
```

## 🐳 Docker развертывание

### Стандартное развертывание
```bash
# Сборка и запуск
docker-compose up -d

# Просмотр логов
docker-compose logs -f app
```

### Production развертывание
```bash
# С Nginx reverse proxy
docker-compose --profile production up -d
```

## 🔧 Обслуживание

### Резервное копирование базы данных
```bash
# Создание резервной копии
cp ai_study.db ai_study.db.backup.$(date +%Y%m%d_%H%M%S)

# Или с помощью SQLite
sqlite3 ai_study.db ".backup backup_$(date +%Y%m%d_%H%M%S).db"
```

### Восстановление базы данных
```bash
# Восстановление из резервной копии
cp ai_study.db.backup.YYYYMMDD_HHMMSS ai_study.db

# Применение миграций после восстановления
python migration_manager.py migrate
```

### Очистка логов
```bash
# Очистка логов приложения
> app.log

# Или удаление старых логов
find . -name "*.log" -mtime +7 -delete
```

## 🚨 Устранение неполадок

### Проблемы с базой данных
```bash
# Проверка схемы базы данных
sqlite3 ai_study.db ".schema"

# Проверка таблиц
sqlite3 ai_study.db ".tables"

# Проверка миграций
sqlite3 ai_study.db "SELECT * FROM migrations ORDER BY applied_at;"
```

### Проблемы с миграциями
```bash
# Если миграция застряла, можно пометить её как примененную
sqlite3 ai_study.db "INSERT INTO migrations (migration_name) VALUES ('migration_name');"

# Или удалить запись о миграции для повторного применения
sqlite3 ai_study.db "DELETE FROM migrations WHERE migration_name = 'migration_name';"
```

### Сброс базы данных (ОСТОРОЖНО!)
```bash
# Полный сброс - удалит ВСЕ данные
rm ai_study.db
python migration_manager.py migrate
python -c "from app import init_db; init_db()"
```

## 📝 Логирование

Приложение ведет логи в файл `app.log`. Уровни логирования:
- `INFO` - общая информация о работе
- `WARNING` - предупреждения
- `ERROR` - ошибки
- `DEBUG` - отладочная информация (только в режиме разработки)

## 🔐 Безопасность

### Рекомендации для production
1. Используйте сильный `SECRET_KEY`
2. Настройте HTTPS
3. Ограничьте доступ к файлу базы данных
4. Регулярно создавайте резервные копии
5. Мониторьте логи на предмет подозрительной активности

### Переменные окружения для production
```env
FLASK_ENV=production
SECRET_KEY=very-strong-secret-key-here
OPENAI_API_KEY=your-openai-key
MAX_UPLOAD_MB=200
MAX_TEXT_CHARS=50000
```