#!/bin/bash
set -e

echo "=== 天机 v9.1 Docker Entrypoint ==="
echo "Port: ${AI_MEMORY_PORT:-8778}"
echo "DB: ${AI_MEMORY_DB:-/app/data/icme.db}"

# 数据目录初始化
mkdir -p /app/data /app/logs

# 数据库初始化（如果不存在则创建）
if [ ! -f "${AI_MEMORY_DB:-/app/data/icme.db}" ]; then
    echo "Initializing database..."
    python -c "from pathlib import Path; from core.sqlite_store import SQLiteMemoryStore; SQLiteMemoryStore(Path('${AI_MEMORY_DB:-/app/data/icme.db}'))"
    echo "Database initialized."
fi

echo "Starting tianji service..."
exec "$@"
