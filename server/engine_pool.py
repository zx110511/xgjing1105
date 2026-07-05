"""
ICME 引擎专用线程池
=================
独立于 uvicorn 默认池（仅~12 workers），为 SQLite 线程本地连接提供充足 worker。
"""
from concurrent.futures import ThreadPoolExecutor

_ENGINE_POOL = ThreadPoolExecutor(
    max_workers=200,
    thread_name_prefix="icme_engine"
)


def get_engine_pool():
    return _ENGINE_POOL
