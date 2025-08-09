# Исправление ограничений PPTX файлов

## Проблема
Пользователи с планами FREE и LITE могли загружать PPTX файлы, хотя согласно конфигурации планов подписки, поддержка PPTX должна быть доступна только в планах STARTER, BASIC и PRO.

## Причина
В маршруте `/upload` отсутствовала проверка плана подписки для PPTX файлов. Функция `allowed_file()` проверяла только расширение файла, но не учитывала ограничения плана.

## Исправление

### 1. Добавлена проверка плана подписки для PPTX
В файле `app.py` в маршруте `/upload` добавлена проверка:

```python
# Дополнительная проверка для PPTX файлов - проверяем план подписки
file_ext = Path(file.filename).suffix.lower()
if file_ext == '.pptx':
    allowed, message = subscription_manager.check_pptx_support(current_user.id)
    if not allowed:
        flash(message, 'error')
        return redirect(url_for('index'))
```

### 2. Исправлено сообщение об ошибке
В файле `subscription_manager.py` исправлено сообщение об ошибке:

**Было:**
```
"Загрузка PPTX файлов доступна только в планах BASIC и PRO. Обновите план для продолжения."
```

**Стало:**
```
"Загрузка PPTX файлов доступна только в планах STARTER, BASIC и PRO. Обновите план для продолжения."
```

## Конфигурация планов

| План     | PPTX поддержка |
|----------|----------------|
| FREEMIUM | ❌ Нет         |
| LITE     | ❌ Нет         |
| STARTER  | ✅ Да          |
| BASIC    | ✅ Да          |
| PRO      | ✅ Да          |

## Тестирование
Создан тест `test_pptx_restriction_fix.py` который проверяет:
- ✅ Корректность ограничений для всех планов
- ✅ Правильность сообщений об ошибках
- ✅ Соответствие конфигурации планов

## Результат
Теперь пользователи с планами FREE и LITE получат сообщение об ошибке при попытке загрузить PPTX файл и будут перенаправлены на страницу обновления плана.

### 3. Обновлен интерфейс пользователя
В файле `templates/index.html` добавлена условная логика:

```html
{% if user_subscription and user_subscription.limits.pptx_support %}
<div class="file-type">
    <i class="fas fa-file-powerpoint" style="color: #d97706;"></i>
    <span>PowerPoint (PPTX)</span>
</div>
{% else %}
<div class="file-type disabled" title="Доступно в планах STARTER, BASIC и PRO">
    <i class="fas fa-file-powerpoint" style="color: #9ca3af;"></i>
    <span style="color: #9ca3af;">PowerPoint (PPTX) 🔒</span>
</div>
{% endif %}
```

### 4. Динамический атрибут accept
Атрибут `accept` в форме загрузки теперь изменяется в зависимости от плана:

```html
accept="{% if user_subscription and user_subscription.limits.pptx_support %}.pdf,.pptx,.mp4,.mov,.mkv{% else %}.pdf,.mp4,.mov,.mkv{% endif %}"
```

## Файлы изменены
- `AITech/app.py` - добавлена проверка плана для PPTX
- `AITech/subscription_manager.py` - исправлено сообщение об ошибке
- `AITech/templates/index.html` - условное отображение PPTX и динамический accept
- `AITech/test_pptx_restriction_fix.py` - базовый тест исправления
- `AITech/test_complete_pptx_fix.py` - полный интеграционный тест