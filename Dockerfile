# Многоэтапная сборка для оптимизации размера образа
FROM python:3.10-slim as builder

# Установка зависимостей для сборки
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Копирование requirements и установка Python зависимостей
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Финальный образ
FROM python:3.10-slim

# Установка runtime зависимостей
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libgomp1 \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Создание пользователя для безопасности
RUN useradd -m -u 1000 appuser

# Копирование Python пакетов из builder
COPY --from=builder /root/.local /home/appuser/.local

# Установка рабочей директории
WORKDIR /app

# Копирование файлов приложения
COPY --chown=appuser:appuser . .

# Создание необходимых директорий
RUN mkdir -p uploads && \
    chown -R appuser:appuser /app

# Переключение на непривилегированного пользователя
USER appuser

# Добавление локальных пакетов в PATH
ENV PATH=/home/appuser/.local/bin:$PATH

# Переменные окружения
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1

# Порт приложения
EXPOSE 5000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# Запуск приложения через gunicorn
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "--timeout", "300", "--access-logfile", "-", "--error-logfile", "-", "app:app"]