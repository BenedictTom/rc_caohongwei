# 单容器同进程并起 mock_provider（内部 :8500）+ uvicorn（对外 :8000）。
# 适配 Fly.io 部署：DATABASE_URL 默认指向 /data/ 卷挂载点。
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_URL=sqlite:////data/notifications.db

# 预创建 /data：挂了 volume 会被覆盖；没挂卷（如 Zeabur 免费层）时 SQLite 仍可写入
# 重启会清空，但容器不会启动失败。
RUN mkdir -p /data

RUN pip install --no-cache-dir uv

# pyproject + 源码先装依赖，让 layer cache 命中：tools / providers 改动不重装
COPY pyproject.toml README.md ./
COPY app/ ./app/
RUN uv pip install --system -e .

COPY tools/ ./tools/
COPY providers.yaml ./

EXPOSE 8000

# mock 后台、uvicorn 前台（容器主进程，接管 PID 1 信号）
CMD ["sh", "-c", "python tools/mock_provider.py --port 8500 --fail-rate 0.10 & exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
