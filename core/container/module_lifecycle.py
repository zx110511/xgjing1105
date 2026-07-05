"""模块生命周期数据类 — 从tianji_container.py提取"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ModuleState(str, Enum):
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    RUNNING = "running"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class ModuleDescriptor:
    name: str
    display_name: str
    category: str
    init_fn: Callable[[], Any]
    start_fn: Optional[Callable[[Any], None]] = None
    stop_fn: Optional[Callable[[Any], None]] = None
    health_fn: Optional[Callable[[Any], Dict]] = None
    depends_on: List[str] = field(default_factory=list)
    critical: bool = False
    init_timeout: float = 30.0


@dataclass
class ModuleInstance:
    descriptor: ModuleDescriptor
    state: ModuleState = ModuleState.UNINITIALIZED
    instance: Any = None
    error: Optional[str] = None
    init_time_ms: float = 0.0
    last_health_check: Optional[float] = None


