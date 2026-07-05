# === Stage 1: Builder ===
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# === Stage 2: Runtime ===
FROM python:3.12-slim AS runtime

LABEL maintainer="tianji-team" \
    version="9.1.0" \
    description="天机 Memory Engine v9.1"

# 安全：非root运行
RUN groupadd -r tianji && useradd -r -g tianji -m tianji

WORKDIR /app

# 从builder阶段拷贝依赖
COPY --from=builder /install /usr/local

# 拷贝源码（.dockerignore排除不需要的）
COPY . .

# entrypoint 脚本（需在切换到 tianji 用户前 chmod）
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# 数据目录
RUN mkdir -p /app/data /app/logs && chown -R tianji:tianji /app

USER tianji

# 环境变量
ENV AI_MEMORY_PORT=8778 \
    AI_MEMORY_ROOT=/app \
    AI_MEMORY_DB=/app/data/icme.db \
    TIANJI_LOG_LEVEL=INFO \
    TIANJI_V91_PROTOCOL_MODE=true \
    TIANJI_V91_EVENT_WIRING=true \
    PYTHONPATH=/app

EXPOSE 8778

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8778/api/health')" || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8778"]
