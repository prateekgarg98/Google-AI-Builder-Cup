FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY gateway ./gateway

ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "python -m flask --app gateway.app run --host=0.0.0.0 --port=${PORT:-8080}"]