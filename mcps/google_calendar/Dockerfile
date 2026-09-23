FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY mcps/google_calendar/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mcps/google_calendar/app.py .

EXPOSE 8002

CMD ["python", "app.py"]
