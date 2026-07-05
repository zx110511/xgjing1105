"""
API路由公共工具函数 v6.0
=========================
消除重复代码：统一 _safe_memory_response() 和 _run()
所有路由模块应从此处导入，禁止本地重新定义。
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from core.shared.models import MemoryResponse

_engine_pool = ThreadPoolExecutor(
    max_workers=200,
    thread_name_prefix="icme_engine"
)


def get_engine_pool():
    """获取ICME引擎专用线程池"""
    return _engine_pool


def safe_memory_response(entry):
    """
    统一的记忆响应序列化（兼容dict和object输入）
    
    Args:
        entry: dict或具有to_dict()方法的对象
        
    Returns:
        MemoryResponse: 标准化的响应对象
    """
    d = entry if isinstance(entry, dict) else entry.to_dict()
    try:
        return MemoryResponse(**d)
    except Exception:
        d.setdefault("size_bytes", len(d.get("content", "").encode("utf-8")))
        d.setdefault("value_score", 0.5)
        d.setdefault("access_count", 0)
        d.setdefault("metadata", {})
        d.setdefault("tags", [])
        d.setdefault("priority", "medium")
        return MemoryResponse(**{k: v for k, v in d.items() if k in MemoryResponse.model_fields})


async def run_sync(fn, *args, **kwargs):
    """
    在线程池中执行同步引擎操作
    
    Args:
        fn: 要执行的同步函数
        *args: 位置参数
        **kwargs: 关键字参数
        
    Returns:
        函数执行结果
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_engine_pool, lambda: fn(*args, **kwargs))
