# Docker Setup для AI Study MVP

## 🚀 Быстрый старт

### 1. Предварительные требования
- Docker 20.10+
- Docker Compose 1.29+
- (Опционально) NVIDIA Docker для GPU поддержки

### 2. Подготовка
```bash
# Клонирование репозитория
git clone https://github.com/Xenox-developer/Junior-ML-Contest.git
cd Junior-ML-Contest

# Создание .env файла
cp .env.example .env
# Отредактируйте .env и добавьте ваш OPENAI_API_KEY

# Сделать скрипты исполняемыми
chmod +x build.sh run-docker.sh
```

### 3. Сборка и запуск

#### Вариант 1: CPU версия (рекомендуется для начала)
```bash
# Сборка
docker-compose build

# Запуск
docker-compose up -d

# Просмотр логов
docker-compose logs -f app
```

#### Вариант 2: GPU версия
```bash
# Убедитесь, что установлен NVIDIA Docker
# Сборка и запуск
docker-compose -f docker-compose.gpu.yml up -d
```

#### Вариант 3: Режим разработки
```bash
# Запуск с hot-reload
docker-compose -f docker-compose.dev.yml up
```

#### Вариант 4: Production с Nginx
```bash
# Запуск с Nginx reverse proxy
docker-compose --profile production up -d
```

## 📁 Структура файлов

```
.
├── Dockerfile              # Основной образ (CPU)
├── Dockerfile.gpu          # GPU версия с CUDA
├── docker-compose.yml      # Основная конфигурация
├── docker-compose.dev.yml  # Конфигурация для разработки
├── docker-compose.gpu.yml  # Конфигурация для GPU
├── .dockerignore          # Исключаемые файлы
├── nginx.conf             # Конфигурация Nginx
├── build.sh               # Скрипт сборки
└── run-docker.sh          # Скрипт запуска
```

## 🔧 Конфигурация

### Переменные окружения (.env)
```env
# Обязательные
OPENAI_API_KEY=sk-...

# Опциональные
MAX_UPLOAD_MB=200
MAX_TEXT_CHARS=50000  # Лимит символов для обработки (20-25 страниц)
FLASK_ENV=production
SECRET_KEY=your-secret-key-here
```

## 📄 Обработка больших документов

### Новые возможности (v2.0)
- **Поддержка документов до 20+ страниц** (50,000 символов)
- **Умное разбиение на части** с сохранением контекста
- **Объединение результатов** из разных частей документа
- **Оптимизированная генерация флеш-карт** для больших текстов

### Лимиты обработки
- **Размер файла**: до 200 МБ (PDF, видео)
- **Текст для анализа**: до 50,000 символов (~20-25 страниц)
- **Автоматическое разбиение**: для документов больше 15,000 символов
- **Флеш-карты**: до 20 карточек для больших документов

### Как работает обработка больших документов
1. **Малые тексты** (до 15К символов) - обрабатываются целиком
2. **Средние тексты** (15К-50К символов) - извлекаются ключевые разделы
3. **Большие тексты** (50К+ символов) - разбиваются на части с умным объединением результатов

### Volumes
- `./uploads:/app/uploads` - загруженные файлы
- `./data:/app/data` - база данных SQLite
- `whisper_cache` - кэш моделей Whisper
- `huggingface_cache` - кэш моделей HuggingFace

## 🛠️ Управление

### Основные команды
```bash
# Запуск
docker-compose up -d

# Остановка
docker-compose down

# Перезапуск
docker-compose restart

# Просмотр логов
docker-compose logs -f app

# Вход в контейнер
docker-compose exec app bash

# Очистка volumes
docker-compose down -v
```

### Обновление
```bash
# Получить последние изменения
git pull

# Пересобрать образы
docker-compose build --no-cache

# Перезапустить
docker-compose up -d
```

## 🔍 Отладка

### Проверка статуса
```bash
# Статус контейнеров
docker-compose ps

# Использование ресурсов
docker stats

# Проверка здоровья
docker-compose exec app curl http://localhost:5000/
```

### Общие проблемы

1. **Out of memory при обработке видео**
   - Увеличьте лимиты памяти в docker-compose.yml
   - Используйте GPU версию для больших файлов

2. **Медленная обработка**
   - Рассмотрите использование GPU версии
   - Проверьте, что модели кэшируются в volumes

3. **Permission denied**
   - Проверьте права на директории uploads и data
   - `sudo chown -R 1000:1000 uploads data`

## 🚀 Оптимизация производительности

### 1. Использование GPU
```yaml
# В docker-compose.gpu.yml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

### 2. Настройка памяти
```yaml
# Увеличение лимитов
deploy:
  resources:
    limits:
      memory: 16G
    reservations:
      memory: 8G
```

### 3. Кэширование моделей
Модели автоматически кэшируются в named volumes для быстрого повторного использования.

## 🔒 Безопасность

1. **Используйте secrets для API ключей**
   ```yaml
   secrets:
     openai_key:
       file: ./secrets/openai_key.txt
   ```

2. **Ограничьте сетевой доступ**
   ```yaml
   networks:
     ai_study_network:
       internal: true
   ```

3. **Регулярно обновляйте образы**
   ```bash
   docker-compose pull
   docker-compose build --no-cache
   ```

## 📊 Мониторинг

### Простой мониторинг
```bash
# Создайте docker-compose.monitoring.yml
services:
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
  
  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
```