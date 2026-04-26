FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY backend/app ./app
COPY frontend ./frontend

# Создание директории для данных
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
