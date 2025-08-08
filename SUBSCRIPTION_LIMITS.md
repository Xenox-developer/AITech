# Система ограничений подписки

## Обзор

Система ограничений подписки реализует трехуровневую модель планов (STARTER, BASIC, PRO) с различными лимитами и функциями для контроля использования ресурсов платформы AI Study.

## Планы подписки

### STARTER (₽0 - навсегда)
- **Анализы в месяц**: 3
- **PDF страницы**: до 5
- **Видео**: до 10 минут
- **AI чат**: 5 сообщений/месяц
- **Функции**: базовые флеш-карты, экспорт с водяным знаком
- **Приоритетная обработка**: нет
- **API доступ**: нет

### BASIC (₽699/месяц)
- **Анализы в месяц**: 25
- **PDF страницы**: до 20
- **Видео**: до 1 часа
- **AI чат**: 500 сообщений/месяц
- **Функции**: полные флеш-карты, Mind Maps, экспорт без водяных знаков
- **Приоритетная обработка**: нет
- **API доступ**: нет

### PRO (₽1399/месяц) - Популярный
- **Анализы в месяц**: безлимитно
- **PDF страницы**: до 100
- **Видео**: до 2 часов
- **AI чат**: безлимитно
- **Функции**: все функции, интерактивные Mind Maps, планы обучения
- **Приоритетная обработка**: да
- **API доступ**: да

## Архитектура системы

### Основные компоненты

1. **SubscriptionManager** (`subscription_manager.py`)
   - Управление подписками и проверка лимитов
   - Отслеживание использования ресурсов
   - Сброс месячных лимитов

2. **Декораторы** (`subscription_decorators.py`)
   - `@require_subscription_limit()` - проверка лимитов
   - `@track_usage()` - отслеживание использования
   - `@subscription_required()` - проверка плана

3. **База данных**
   - Расширенная таблица `users` с полями подписки
   - Таблица `subscription_usage` для истории использования
   - Таблица `subscription_history` для истории изменений планов

### Структура базы данных

```sql
-- Дополнительные поля в таблице users
ALTER TABLE users ADD COLUMN subscription_type TEXT DEFAULT 'starter';
ALTER TABLE users ADD COLUMN subscription_start_date TIMESTAMP;
ALTER TABLE users ADD COLUMN subscription_end_date TIMESTAMP;
ALTER TABLE users ADD COLUMN monthly_analyses_used INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN monthly_reset_date TIMESTAMP;
ALTER TABLE users ADD COLUMN total_pdf_pages_used INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN total_video_minutes_used INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN ai_chat_messages_used INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN subscription_status TEXT DEFAULT 'active';

-- Таблица отслеживания использования
CREATE TABLE subscription_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    usage_type TEXT NOT NULL,
    amount INTEGER DEFAULT 1,
    resource_info TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Таблица истории подписок
CREATE TABLE subscription_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    old_plan TEXT,
    new_plan TEXT,
    change_reason TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

## Использование в коде

### Проверка лимитов с декораторами

```python
from subscription_decorators import require_subscription_limit, track_usage

@app.route('/upload', methods=['POST'])
@login_required
@require_subscription_limit('analysis')  # Проверяем лимит анализов
@track_usage('analysis')  # Отслеживаем использование
def upload_file():
    # Логика загрузки файла
    pass

@app.route('/api/chat/<int:result_id>', methods=['POST'])
@login_required
@require_subscription_limit('ai_chat')  # Проверяем лимит AI чата
@track_usage('ai_chat')  # Отслеживаем использование
def chat_with_lecture(result_id):
    # Логика AI чата
    pass
```

### Ручная проверка лимитов

```python
from subscription_manager import subscription_manager

# Проверка лимита PDF страниц
allowed, message = subscription_manager.check_pdf_pages_limit(user_id, pages_count)
if not allowed:
    flash(message, 'error')
    return redirect(url_for('index'))

# Проверка лимита длительности видео
allowed, message = subscription_manager.check_video_duration_limit(user_id, duration_minutes)
if not allowed:
    raise Exception(message)

# Проверка доступа к функции
if not subscription_manager.check_feature_access(user_id, 'interactive_mind_maps'):
    return jsonify({'error': 'Функция недоступна в вашем плане'})
```

### Запись использования ресурсов

```python
# Запись использования анализа
subscription_manager.record_usage(user_id, 'analysis', 1, filename)

# Запись использования PDF страниц
subscription_manager.record_usage(user_id, 'pdf_pages', pages_count, filename)

# Запись использования AI чата
subscription_manager.record_usage(user_id, 'ai_chat', 1, 'conversation')
```

## API эндпоинты

### GET /subscription_status
Получение статуса подписки пользователя

**Ответ:**
```json
{
    "success": true,
    "subscription": {
        "type": "basic",
        "status": "active",
        "monthly_analyses_used": 5,
        "monthly_reset_date": "2025-02-07T10:30:00"
    },
    "usage_stats": {
        "plan": "basic",
        "analyses": {
            "used": 5,
            "limit": 25,
            "unlimited": false
        },
        "ai_chat": {
            "used": 120,
            "limit": 500,
            "unlimited": false
        }
    }
}
```

### POST /upgrade_subscription
Обновление плана подписки

**Запрос:**
```json
{
    "plan": "pro"
}
```

**Ответ:**
```json
{
    "success": true,
    "message": "План успешно изменен на PRO"
}
```

## Интеграция с UI

### Отображение лимитов в дашборде

```html
<!-- Информация о подписке -->
{% if usage_stats %}
<div class="subscription-info mb-4">
    <div class="card border-0 shadow-sm">
        <div class="card-body">
            <h5 class="card-title">
                <i class="fas fa-crown text-warning me-2"></i>
                План подписки: <span class="badge bg-primary">{{ usage_stats.plan.upper() }}</span>
            </h5>
            <div class="row">
                <div class="col-sm-6">
                    <small class="text-muted">Анализы в месяц:</small>
                    {% if usage_stats.analyses.unlimited %}
                        <div class="fw-bold text-success">{{ usage_stats.analyses.used }} (безлимитно)</div>
                    {% else %}
                        <div class="progress mt-1" style="height: 6px;">
                            <div class="progress-bar" style="width: {{ (usage_stats.analyses.used / usage_stats.analyses.limit * 100) if usage_stats.analyses.limit > 0 else 0 }}%"></div>
                        </div>
                        <small>{{ usage_stats.analyses.used }}/{{ usage_stats.analyses.limit }}</small>
                    {% endif %}
                </div>
            </div>
        </div>
    </div>
</div>
{% endif %}
```

### Страница планов подписки

Создана страница `/pricing` с интерактивными карточками планов, FAQ и возможностью мгновенного обновления плана.

## Автоматические процессы

### Сброс месячных лимитов

Система автоматически сбрасывает месячные лимиты (анализы, AI чат) при достижении даты `monthly_reset_date`. Сброс происходит при каждой проверке лимитов.

### Отслеживание использования

Все действия пользователей автоматически записываются в таблицу `subscription_usage` для аналитики и биллинга.

## Безопасность

1. **Проверка на стороне сервера**: все лимиты проверяются на backend
2. **Декораторы**: автоматическая проверка лимитов через декораторы
3. **Логирование**: все действия с подписками логируются
4. **Валидация**: проверка корректности планов и лимитов

## Тестирование

Создан тестовый файл `test_subscription_limits.py` для проверки всех аспектов системы ограничений:

```bash
python test_subscription_limits.py
```

Тест проверяет:
- Все планы подписки
- Лимиты для каждого типа ресурсов
- Доступ к функциям
- Запись использования
- Статистику использования

## Расширение системы

Для добавления новых лимитов или планов:

1. Обновите `SUBSCRIPTION_PLANS` в `subscription_manager.py`
2. Добавьте новые методы проверки в `SubscriptionManager`
3. Создайте соответствующие декораторы в `subscription_decorators.py`
4. Обновите UI шаблоны для отображения новых лимитов
5. Добавьте тесты в `test_subscription_limits.py`

## Мониторинг и аналитика

Система предоставляет данные для:
- Отслеживания использования ресурсов
- Анализа популярности функций
- Прогнозирования нагрузки
- Оптимизации планов подписки