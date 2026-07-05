# 天机v9.0 元初系统 · 智能记忆平台
# ================================
# 独立Docker容器，完全解耦Trae IDE

FROM python:3.12-slim

LABEL org.opencontainers.image.title="天机v9.0 元初系统"
LABEL org.opencontainers.image.description="ICME六层记忆引擎 - 平台级服务"
LABEL org.opencontainers.image.version="3.0.0"

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV AI_MEMORY_ROOT=/app
ENV AI_MEMORY_DATA=/app/data/.memory
ENV AI_MEMORY_HOST=0.0.0.0
ENV AI_MEMORY_PORT=8765

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data/.memory/{sensory,working,short_term,episodic,semantic,meta}

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/health')" || exit 1

CMD ["python", "-m", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8765"]
