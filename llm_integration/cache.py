r"""
LLM响应缓存
============
基于SHA256的响应去重缓存。
"""

import time
import hashlib
from typing import Any, Dict, Optional
from collections import OrderedDict


class ResponseCache:
    def __init__(self, ttl: int = 3600, max_size: int = 500):
        self.ttl = ttl
        self.max_size = max_size
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    def key(self, prompt: str, model: str = "deepseek") -> str:
        return hashlib.sha256(f"{model}:{prompt}".encode()).hexdigest()

    def get(self, cache_key: str) -> Optional[Any]:
        if cache_key in self._store:
            ts, value = self._store[cache_key]
            if time.time() - ts < self.ttl:
                self._store.move_to_end(cache_key)
                return value
            del self._store[cache_key]
        return None

    def set(self, cache_key: str, value: Any):
        if len(self._store) >= self.max_size:
            self._store.popitem(last=False)
        self._store[cache_key] = (time.time(), value)

    def clear(self):
        self._store.clear()

    @property
    def size(self) -> int:
        return len(self._store)
