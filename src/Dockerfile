FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все модули проекта
COPY main.py .
COPY config.py .
COPY keyboards.py .
COPY states.py .
COPY utils.py .
COPY handlers.py .

CMD ["python", "main.py"]

