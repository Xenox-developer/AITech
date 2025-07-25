#!/bin/bash

echo "🚀 Запуск AI-конспект с системой аутентификации"
echo "================================================"

# Проверяем виртуальное окружение
if [ ! -d "venv" ]; then
    echo "❌ Виртуальное окружение не найдено. Создаем..."
    python3 -m venv venv
fi

# Активируем виртуальное окружение
echo "🔧 Активация виртуального окружения..."
source venv/bin/activate

# Устанавливаем зависимости
echo "📦 Установка зависимостей..."
pip install Flask Flask-Login Flask-WTF

# Инициализируем базу данных
echo "🗄️ Инициализация базы данных..."
python init_database.py

# Создаем демо-пользователей
echo "👥 Создание демо-пользователей..."
python demo_auth.py

echo ""
echo "✅ Система готова к запуску!"
echo ""
echo "🔑 Тестовые аккаунты:"
echo "   admin@ai-konspekt.ru / admin123 (Premium)"
echo "   student@example.com / student123 (Free)"
echo "   teacher@university.edu / teacher123 (Premium)"
echo ""
echo "🌐 Запуск приложения..."
echo "   Откройте браузер: http://localhost:5000"
echo ""

# Запускаем приложение
python app.py