r"""
天机v9.1 - 多平台适配基础层
=============================
统一的平台SDK接口定义和HTTP客户端
各平台适配器继承此基类
"""

import json
import time
import requests
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from abc import ABC, abstractmethod


@dataclass
class MemorySDKConfig:
    base_url: str = "http://127.0.0.1:8771"
    api_key: Optional[str] = None
    platform: str = "generic"
    timeout: int = 30
    retry_count: int = 3
    auto_batch: bool = True
    batch_size: int = 50
    batch_interval: float = 5.0

    def __post_init__(self):
        self.base_url = self.base_url.rstrip("/")


class PlatformAdapter(ABC):
    def __init__(self, config: MemorySDKConfig = None):
        self.config = config or MemorySDKConfig()
        self._pending_batch: List[Dict] = []

    @abstractmethod
    def on_event(self, event_type: str, payload: Dict[str, Any]) -> Dict:
        pass

    @abstractmethod
    def get_platform_info(self) -> Dict[str, str]:
        pass

    def remember(
        self, content: str, layer: str = "working",
        tags: List[str] = None, priority: str = "medium",
        metadata: Dict = None,
    ) -> Optional[Dict]:
        payload = {
            "content": content,
            "layer": layer,
            "tags": tags or [],
            "priority": priority,
            "metadata": metadata or {},
            "platform": self.config.platform,
        }
        return self._post("/api/platform/remember", payload)

    def recall(
        self, query: str, limit: int = 20,
    ) -> Optional[List[Dict]]:
        return self._get("/api/platform/recall", {
            "query": query,
            "platform": self.config.platform,
            "limit": limit,
        })

    def send_event(self, event_type: str, payload: Dict[str, Any]) -> Optional[Dict]:
        event = {
            "event_type": event_type,
            "platform": self.config.platform,
            "payload": payload,
        }
        return self._post("/api/platform/event", event)

    def batch_remember(self, entry: Dict):
        if self.config.auto_batch:
            self._pending_batch.append(entry)
            if len(self._pending_batch) >= self.config.batch_size:
                self.flush_batch()
        else:
            self.remember(**entry)

    def flush_batch(self):
        if not self._pending_batch:
            return
        for entry in self._pending_batch:
            self.remember(**entry)
        self._pending_batch.clear()

    def health_check(self) -> Optional[Dict]:
        return self._get("/api/platform/health")

    def get_platform_stats(self) -> Optional[Dict]:
        return self._get(f"/api/platform/stats/{self.config.platform}")

    def _get(self, path: str, params: Dict = None) -> Optional[Dict]:
        for attempt in range(self.config.retry_count):
            try:
                resp = requests.get(
                    f"{self.config.base_url}{path}",
                    params=params,
                    headers=self._headers(),
                    timeout=self.config.timeout,
                )
                if resp.status_code == 200:
                    return resp.json()
            except requests.RequestException as e:
                if attempt == self.config.retry_count - 1:
                    print(f"[{self.config.platform}] API error: {e}")
                else:
                    time.sleep(1 * (attempt + 1))
        return None

    def _post(self, path: str, data: Dict) -> Optional[Dict]:
        for attempt in range(self.config.retry_count):
            try:
                resp = requests.post(
                    f"{self.config.base_url}{path}",
                    json=data,
                    headers=self._headers(),
                    timeout=self.config.timeout,
                )
                if resp.status_code in (200, 201):
                    return resp.json()
            except requests.RequestException as e:
                if attempt == self.config.retry_count - 1:
                    print(f"[{self.config.platform}] API error: {e}")
                else:
                    time.sleep(1 * (attempt + 1))
        return None

    def _headers(self) -> Dict:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers
