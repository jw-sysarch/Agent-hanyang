FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY mcps/kakao_map/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mcps/kakao_map/ .

EXPOSE 8006

CMD ["python", "app.py"]
