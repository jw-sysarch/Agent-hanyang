FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY mcps/google_sheets/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mcps/google_sheets/app.py .

EXPOSE 8003

CMD ["python", "app.py"]
