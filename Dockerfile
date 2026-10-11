# LoveYouForever —— 多阶段构建，镜像尽量小
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    LYF_ENV=production

WORKDIR /app

# 先装依赖，蹭 Docker 层缓存
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install gunicorn==23.0.0

COPY . .

RUN mkdir -p instance backups themes app/static/uploads/{covers,photos,moments,avatars} logs && \
    chmod +x install.sh start.sh backup.sh 2>/dev/null || true

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:5000/api/stats')" || exit 1

CMD ["sh", "-c", "python -c 'from app import create_app;from app.extensions import db;app=create_app(\"production\");app.app_context().push();db.create_all()' && gunicorn -w 4 -k gthread --threads 4 -b 0.0.0.0:5000 --access-logfile - wsgi:app"]
