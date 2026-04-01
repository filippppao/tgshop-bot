FROM python:3.10-slim

WORKDIR /app

# Установка системных зависимостей (если понадобятся для определенных пакетов)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements.txt
COPY telegram-shop-bot-master/telegram-shop-bot-master/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходники бота в контейнер
COPY telegram-shop-bot-master/telegram-shop-bot-master/ /app/

# Создаем директорию для базы данных sqlite (будет примаплена как volume)
RUN mkdir -p /app/data && chmod -R 777 /app/data

# Устанавливаем путь до базы данных из переменной окружения
ENV DB_PATH=/app/data/shop.db
# Устанавливаем директорию для фото
ENV PHOTOS_DIR=/app/data/product_photos

# Запуск
CMD ["python", "bot.py"]
