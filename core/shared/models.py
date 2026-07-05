r"""
天机v9.1 - Pydantic数据模型
统一API层的请求/响应模型定义
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MemoryLayer(str, Enum):
    sensory = "sensory"
    working = "working"
    short_term = "short_term"
    episodic = "episodic"
    semantic = "semantic"
    meta = "meta"


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class MemoryCreate(BaseModel):
    content: str
    layer: MemoryLayer = MemoryLayer.working
    tags: List[str] = Field(default_factory=list)
    priority: Priority = Priority.medium
    metadata: Dict[str, Any] = Field(default_factory=dict)
    session_id: Optional[str] = None
    use_llm: Optional[bool] = None  # None=自动(>50字符启用), True=强制启用, False=强制关闭


class MemoryResponse(BaseModel):
    model_config = {"extra": "allow"}

    id: str
    content: str
    layer: str
    tags: List[str]
    priority: str
    value_score: float
    access_count: int
    created_at: float
    last_accessed: float
    size_bytes: int
    metadata: Dict[str, Any] = Field(default_factory=dict)
    asset_id: Optional[str] = None


class MemorySearchQuery(BaseModel):
    query: str
    layers: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    priority: Optional[List[str]] = None
    limit: int = Field(default=20, ge=1, le=100)
    min_score: float = Field(default=0.1, ge=0, le=1)
    semantic: bool = True
    include_archived: bool = False


class MemoryStats(BaseModel):
    model_config = {"extra": "ignore"}

    total_entries: int
    total_accesses: int
    uptime_seconds: float
    layers: Dict[str, int]
    archive_entries: int
    consolidations: int
    archivals: int
    data_path: str
    hit_rate: float = 0.0
    avg_recall_latency_ms: float = 0.0
    rejected: int = 0
    downgraded: int = 0
    conflicts: int = 0
    consolidations_triggered: int = 0
    hard_cap_enforcements: int = 0
    consolidation_events_logged: int = 0
    storage_backend: str = "sqlite"
    db_size_mb: float = 0.0
    recall_rate: float = 0.0
    quality_hits: int = 0
    total_recall_calls: int = 0
    total_recall_hits: int = 0


class AgentInfo(BaseModel):
    id: str
    name: str
    role: str
    description: Optional[str] = None


class ConversationSummary(BaseModel):
    id: str
    title: str
    message_count: int
    created_at: float
    last_active: float
    agent_list: List[str]
    key_decisions: List[str] = Field(default_factory=list)
    summary_text: Optional[str] = None


class SummaryRequest(BaseModel):
    conversation_id: str
    max_length: int = Field(default=500, ge=100, le=2000)
    extract_decisions: bool = True
    language: str = "zh"


class SummaryResponse(BaseModel):
    conversation_id: str
    summary: str
    key_points: List[str]
    decisions: List[Dict[str, str]]
    entities: List[str]
    agent_contributions: Dict[str, int]
    generated_at: float


class PlatformEvent(BaseModel):
    event_type: str
    source: str = "generic"
    payload: Dict[str, Any]
    timestamp: Optional[float] = None
    session_id: Optional[str] = None


class HealthStatus(BaseModel):
    model_config = {"extra": "ignore"}

    status: str
    version: str
    edition: str = "source"
    engine_ready: bool
    embedding_ready: bool
    layers: Dict[str, Dict[str, Any]]
    uptime_seconds: float
    # v9.1: 协议调度与事件织入运行状态 (默认False向后兼容)
    protocol_mode: bool = False
    event_wiring: bool = False


class WebSocketMessage(BaseModel):
    type: str
    data: Dict[str, Any]
    timestamp: float
