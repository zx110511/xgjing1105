"""
远程记忆系统客户端 - 集成自unified-memory-bridge

提供NexusClient和TraeClient用于连接外部记忆服务。
用于统一适配器的双写模式中连接外部系统。
"""

import json
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    import requests as _requests
    _HAS_HTTPX = False


@dataclass
class RemoteMemory:
    id: str
    content: str
    layer: str = "working"
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)
    priority: str = "medium"
    created_at: float = field(default_factory=time.time)
    value_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get(self, key, default=None):
        return getattr(self, key, default) if hasattr(self, key) else default


class BaseRemoteClient:
    def __init__(self, base_url: str, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def close(self):
        pass

    def _get(self, path: str) -> Optional[Dict]:
        if _HAS_HTTPX:
            import httpx
            try:
                r = httpx.get(f"{self.base_url}{path}", timeout=self.timeout)
                r.raise_for_status()
                return r.json()
            except Exception:
                return None
        else:
            import requests
            try:
                r = requests.get(f"{self.base_url}{path}", timeout=self.timeout)
                r.raise_for_status()
                return r.json()
            except Exception:
                return None

    def _post(self, path: str, data: Dict) -> Optional[Dict]:
        if _HAS_HTTPX:
            import httpx
            try:
                r = httpx.post(f"{self.base_url}{path}", json=data, timeout=self.timeout)
                r.raise_for_status()
                return r.json()
            except Exception:
                return None
        else:
            import requests
            try:
                r = requests.post(f"{self.base_url}{path}", json=data, timeout=self.timeout)
                r.raise_for_status()
                return r.json()
            except Exception:
                return None


class NexusClient(BaseRemoteClient):
    def __init__(self, base_url: str = "http://127.0.0.1:8768", timeout: int = 10):
        super().__init__(base_url, timeout)

    def store(self, content: str, layer: str = "working",
              labels: Optional[List[str]] = None) -> str:
        result = self._post("/api/memories", {
            "content": content,
            "category": layer,
            "labels": labels or [],
        })
        if result:
            return result.get("id", "")
        return ""

    def recall(self, query: str, layers: Optional[List[str]] = None,
               limit: int = 10) -> List[Dict]:
        result = self._post("/api/memories/recall", {
            "query": query,
            "limit": limit,
        })
        if result:
            return result.get("results", [])
        return []

    def health_check(self) -> bool:
        try:
            result = self._get("/health")
            return result is not None and result.get("status") == "healthy"
        except Exception:
            return False

    def trigger_dream(self) -> Dict[str, Any]:
        result = self._post("/api/memories/dream", {})
        return result or {"status": "error"}


class TraeClient(BaseRemoteClient):
    def __init__(self, base_url: str = "http://127.0.0.1:8000", timeout: int = 10):
        super().__init__(base_url, timeout)

    def store(self, content: str, layer: str = "working",
              labels: Optional[List[str]] = None,
              priority: str = "medium") -> str:
        result = self._post("/api/memory/remember", {
            "content": content,
            "layer": layer,
            "tags": labels or [],
            "priority": priority,
        })
        if result:
            return result.get("entry_id", result.get("id", ""))
        return ""

    def recall(self, query: str, layers: Optional[List[str]] = None,
               limit: int = 10) -> List[Dict]:
        result = self._post("/api/memory/recall", {
            "query": query,
            "layers": layers or ["working", "short_term", "episodic"],
            "limit": limit,
        })
        if result:
            return result.get("results", result.get("entries", []))
        return []

    def health_check(self) -> bool:
        try:
            result = self._get("/api/health")
            return result is not None and result.get("status") == "healthy"
        except Exception:
            return False
