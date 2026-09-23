FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY mcps/gmail/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mcps/gmail/app.py .

EXPOSE 8008

CMD ["python", "app.py"]
