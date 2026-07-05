r"""
天机记忆系统 (TIANJI) - core.memory 子包  [v10-ready]
====================================================
ICME 引擎职责拆分子包。将原 core/engine.py 的庞大 ICMEEngine 类
按职责拆分为四个独立协作组件：

- MemoryWriter     记忆写入   (remember / batch / 质量门禁 / 资产注册)
- PromotionEngine  层级晋升   (consolidate / promotion_score / 自动固结)
- ArchiveManager   归档与容量 (forget / 驱逐 / size tracking)
- MemoryIndex      检索与索引 (recall / 评分 / tag 索引)

[v10-ready] 设计原则:
- 各组件通过构造函数接收 engine (宿主) 作为共享上下文与依赖注入入口
- 组件之间不互相 import，统一通过宿主 (回调机制) 协作，避免循环依赖
- MemoryEntry 数据模型在此定义，供 engine 与各子模块共享
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MemoryEntry:
    id: str
    content: str
    layer: str
    tags: list[str] = field(default_factory=list)
    priority: str = "medium"
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    effectiveness_score: float = 0.5
    related_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    changelog: list[dict] = field(default_factory=list)

    @property
    def size_bytes(self) -> int:
        return (
            len(self.content.encode("utf-8"))
            + len(json.dumps(self.tags))
            + len(json.dumps(self.metadata))
        )

    def priority_weight(self) -> float:
        weights = {"critical": 5.0, "high": 4.0, "medium": 2.0, "low": 1.0}
        return weights.get(self.priority, 1.0)

    def value_score(self) -> float:
        recency_factor = max(
            0.1, 1.0 - (time.time() - self.last_accessed) / (30 * 24 * 3600)
        )
        return (
            self.priority_weight() * 0.4
            + self.effectiveness_score * 0.3
            + recency_factor * 0.2
            + min(1.0, self.access_count / 20) * 0.1
        )

    def update_content(self, new_content: str):
        if self.content != new_content:
            self.changelog.append(
                {
                    "timestamp": time.time(),
                    "delta_content": new_content,
                    "previous_content": self.content[:200]
                    if len(self.content) > 200
                    else self.content,
                }
            )
            self.content = new_content
            self.last_accessed = time.time()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "layer": self.layer,
            "tags": self.tags,
            "priority": self.priority,
            "value_score": round(self.value_score(), 4),
            "access_count": self.access_count,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "size_bytes": self.size_bytes,
            "metadata": self.metadata,
            "related_ids": self.related_ids,
        }


# 子模块核心类导出（MemoryEntry 必须先于子模块定义，避免循环依赖）
from .writer import MemoryWriter  # noqa: E402
from .promoter import PromotionEngine  # noqa: E402
from .archiver import ArchiveManager  # noqa: E402
from .indexer import MemoryIndex  # noqa: E402

# ═══════════════════════════════════════════════════════════════
# v9.1新增：时序记忆能力 [v10-ready]
# ═══════════════════════════════════════════════════════════════

# 时序记录模型
try:
    from .temporal_record import (
        TemporalRecord,
        TemporalRecordValidator,
        TemporalQueryBuilder,
        create_temporal_record,
        invalidate_record,
    )
except ImportError:
    pass

# 级联失效器
try:
    from .cascade_invalidator import (
        CascadeInvalidator,
        IInvalidator,
        IGraph,
        InvalidationReport,
    )
except ImportError:
    pass

# 双过程固结器
try:
    from .dual_process import (
        DualProcessConsolidator,
        IConsolidator,
        ConsolidationReport,
        ConsolidationConfig,
    )
except ImportError:
    pass

__all__ = [
    "MemoryEntry",
    "MemoryWriter",
    "PromotionEngine",
    "ArchiveManager",
    "MemoryIndex",
    # v9.1 时序记忆能力
    "TemporalRecord",
    "TemporalRecordValidator",
    "TemporalQueryBuilder",
    "create_temporal_record",
    "invalidate_record",
    "CascadeInvalidator",
    "IInvalidator",
    "IGraph",
    "InvalidationReport",
    "DualProcessConsolidator",
    "IConsolidator",
    "ConsolidationReport",
    "ConsolidationConfig",
]
