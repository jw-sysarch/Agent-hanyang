FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY mcps/google_docs/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mcps/google_docs/app.py .

EXPOSE 8001

CMD ["python", "app.py"]
