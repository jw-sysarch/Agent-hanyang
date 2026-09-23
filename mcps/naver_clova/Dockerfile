FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY mcps/naver_clova/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mcps/naver_clova/app.py .

EXPOSE 8005

CMD ["python", "app.py"]
