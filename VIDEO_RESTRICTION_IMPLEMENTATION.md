# Реализация ограничений видео файлов

## Обзор
Реализованы ограничения на загрузку видео файлов для планов подписки. Теперь загрузка видео доступна только пользователям с планами STARTER, BASIC и PRO.

## Изменения в конфигурации планов

### Добавлено новое поле `video_support`
В структуру `SubscriptionLimits` добавлено поле `video_support: bool` для контроля доступа к видео файлам.

### Конфигурация планов
```python
'freemium': SubscriptionLimits(
    # ... другие параметры ...
    video_support=False,  # Видео недоступно в FREEMIUM
),
'lite': SubscriptionLimits(
    # ... другие параметры ...
    video_support=False,  # Видео недоступно в LITE
),
'starter': SubscriptionLimits(
    # ... другие параметры ...
    video_support=True,   # Видео доступно в STARTER
),
'basic': SubscriptionLimits(
    # ... другие параметры ...
    video_support=True,   # Видео доступно в BASIC
),
'pro': SubscriptionLimits(
    # ... другие параметры ...
    video_support=True,   # Видео доступно в PRO
)
```

## Изменения в backend

### 1. Новая функция проверки поддержки видео
```python
def check_video_support(self, user_id: int) -> Tuple[bool, str]:
    """Проверка поддержки видео файлов"""
    subscription = self.get_user_subscription(user_id)
    if not subscription:
        return False, "Подписка не найдена"
    
    limits = subscription['limits']
    
    if not limits.video_support:
        return False, "Загрузка видео файлов доступна только в планах STARTER, BASIC и PRO. Обновите план для продолжения."
    
    return True, ""
```

### 2. Проверка в маршруте загрузки файлов (`/upload`)
```python
# Дополнительная проверка для видео файлов - проверяем план подписки
if file_ext in ['.mp4', '.mov', '.mkv']:
    allowed, message = subscription_manager.check_video_support(current_user.id)
    if not allowed:
        flash(message, 'error')
        return redirect(url_for('index'))
```

### 3. Проверка в маршруте загрузки видео по URL (`/upload_url`)
```python
# Проверка поддержки видео для плана пользователя
allowed, message = subscription_manager.check_video_support(current_user.id)
if not allowed:
    flash(message, 'error')
    return redirect(url_for('index'))
```

## Изменения в frontend

### 1. Условное отображение видео файлов
```html
{% if user_subscription and user_subscription.limits.video_support %}
<div class="file-type">
    <i class="fas fa-video" style="color: #06b6d4;"></i>
    <span>MP4, MOV, MKV</span>
</div>
{% else %}
<div class="file-type disabled" title="Доступно в планах STARTER, BASIC и PRO">
    <i class="fas fa-video" style="color: #9ca3af;"></i>
    <span style="color: #9ca3af;">MP4, MOV, MKV 🔒</span>
</div>
{% endif %}
```

### 2. Динамический атрибут accept
```html
accept="{% set accepted_formats = ['.pdf'] %}
       {% if user_subscription and user_subscription.limits.pptx_support %}
           {% set _ = accepted_formats.append('.pptx') %}
       {% endif %}
       {% if user_subscription and user_subscription.limits.video_support %}
           {% set _ = accepted_formats.extend(['.mp4', '.mov', '.mkv']) %}
       {% endif %}
       {{ accepted_formats | join(',') }}"
```

### 3. Блокировка вкладки "Видео по ссылке"
```html
{% if user_subscription and user_subscription.limits.video_support %}
<button class="upload-tab" onclick="switchTab('url')">
    <i class="fas fa-link"></i>
    <span>Видео по ссылке</span>
</button>
{% else %}
<button class="upload-tab disabled" title="Доступно в планах STARTER, BASIC и PRO" 
        style="opacity: 0.5; cursor: not-allowed;">
    <i class="fas fa-lock"></i>
    <span>Видео по ссылке 🔒</span>
</button>
{% endif %}
```

### 4. Заглушка для загрузки видео по URL
```html
{% else %}
<div style="text-align: center; padding: 40px 20px;">
    <i class="fas fa-lock upload-icon" style="color: #9ca3af;"></i>
    <h3 class="upload-title" style="color: #9ca3af;">Загрузка видео недоступна</h3>
    <p class="upload-subtitle" style="color: #9ca3af;">
        Загрузка видео доступна только в планах STARTER, BASIC и PRO
    </p>
    <a href="{{ url_for('pricing') }}" class="btn btn-primary" style="margin-top: 20px;">
        <i class="fas fa-arrow-up" style="margin-right: 8px;"></i>
        Обновить план
    </a>
</div>
{% endif %}
```

## Изменения в странице с ценами

### Обновлена информация о видео в планах FREE и LITE
```html
<!-- Было -->
<li class="mb-1">
    <i class="fas fa-check text-success me-2"></i>
    1 видео до 10 минут
</li>

<!-- Стало -->
<li class="mb-1">
    <i class="fas fa-times text-danger me-2"></i>
    Видео недоступно
</li>
```

## Матрица доступности файлов

| План     | PDF | PPTX | Видео |
|----------|-----|------|-------|
| FREEMIUM | ✅  | ❌   | ❌    |
| LITE     | ✅  | ❌   | ❌    |
| STARTER  | ✅  | ✅   | ✅    |
| BASIC    | ✅  | ✅   | ✅    |
| PRO      | ✅  | ✅   | ✅    |

## Тестирование
Созданы комплексные тесты:
- `test_video_restriction_fix.py` - базовый тест ограничений видео
- `test_complete_file_restrictions.py` - полный интеграционный тест всех ограничений

## Файлы изменены
- `AITech/subscription_manager.py` - добавлено поле video_support и функция check_video_support
- `AITech/app.py` - добавлены проверки видео в маршрутах /upload и /upload_url
- `AITech/templates/index.html` - условное отображение видео и блокировка интерфейса
- `AITech/templates/pricing.html` - обновлена информация о видео в планах
- `AITech/test_video_restriction_fix.py` - тест ограничений видео
- `AITech/test_complete_file_restrictions.py` - полный интеграционный тест

## Результат
Теперь пользователи с планами FREE и LITE:
- ❌ Не могут загружать видео файлы через форму
- ❌ Не могут загружать видео по URL
- 🔒 Видят заблокированные элементы интерфейса
- 💬 Получают информативные сообщения об ошибках
- 🔄 Могут обновить план для получения доступа к видео