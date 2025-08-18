# Dockerfile
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN adduser --disabled-password --gecos "" appuser && mkdir -p /data && chown -R appuser /data
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
USER appuser
ENV DB_FILE=/data/shifts.db
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s CMD curl -f http://localhost:8501/_stcore/health || exit 1
CMD ["streamlit","run","main.py","--server.port=8501","--server.address=0.0.0.0"]
