# -*- coding: utf-8-sig -*-
"""天机v10.0.1 通用工具函数  [v10-ready]

无外部依赖的纯函数工具集。

版本: 1.0.0
"""
from __future__ import annotations

import time
import hashlib
import uuid
from typing import Any


def generate_entry_id() -> str:
    """生成记忆条目ID  [v10-ready]"""
    return f"mem_{uuid.uuid4().hex[:12]}"


def generate_asset_id() -> str:
    """生成资产ID  [v10-ready]"""
    return f"ast_{uuid.uuid4().hex[:12]}"


def generate_event_id() -> str:
    """生成事件ID  [v10-ready]"""
    return f"evt_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"


def content_hash(content: str) -> str:
    """计算内容哈希 (SHA-256前16位)  [v10-ready]"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def timestamp_ms() -> int:
    """当前时间戳(毫秒)  [v10-ready]"""
    return int(time.time() * 1000)


def timestamp_s() -> float:
    """当前时间戳(秒)  [v10-ready]"""
    return time.time()


def safe_get(data: dict[str, Any], key: str, default: Any = None) -> Any:
    """安全字典取值  [v10-ready]"""
    try:
        return data.get(key, default)
    except (AttributeError, TypeError):
        return default


def truncate(text: str, max_length: int = 200) -> str:
    """截断文本  [v10-ready]"""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."
