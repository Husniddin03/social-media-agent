#!/bin/bash
# Render uchun startup skript — web server + Telegram listener birga

# Loglarni ko'rsatish
echo "🚀 Starting Django web server + Telegram listener..."

# Migratsiyalarni qo'llash
python manage.py migrate --noinput

# Static fayllarni yig'ish
python manage.py collectstatic --noinput 2>/dev/null || true

# Telegram listener backgroundda ishga tushadi
echo "📡 Starting Telegram listener..."
python manage.py run_telegram_listener &
LISTENER_PID=$!
echo "   Listener PID: $LISTENER_PID"

# Web serverni ishga tushirish
echo "🌐 Starting Gunicorn..."
exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120
