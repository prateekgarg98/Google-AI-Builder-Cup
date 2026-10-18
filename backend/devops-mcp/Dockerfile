FROM python:3.14-slim

WORKDIR /app

COPY server ./server

RUN pip install --no-cache-dir "mcp<2" uvicorn

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Use shell form to respect Cloud Run's dynamic PORT environment variable
CMD uvicorn server.http_app:app --host 0.0.0.0 --port ${PORT}