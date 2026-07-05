# core/memory/temporal_record.py [v10-ready]
"""时序记忆条目模型 — 带双时态戳的记忆记录

设计原则：
- 每条记忆都有 event_time(事件发生时间) 和 record_time(记录时间)
- valid_from / valid_to 表示知识有效窗口（valid_to=None表示当前有效）
- superseded_by 链接到替代本条的新记录（形成版本链）
- 支持"时间旅行查询"：给定时间点t，查询当时有效的知识快照

[v10-ready] 本模块为v10.0.1时序知识图的核心数据结构。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

__all__ = [
    "TemporalRecord",
    "TemporalRecordValidator",
    "TemporalQueryBuilder",
    "invalidate_record",
    "create_temporal_record",
]

# 合法的记忆层级（对应 ICME 六层架构）
_VALID_LAYERS: frozenset[str] = frozenset(
    {"sensory", "working", "short_term", "episodic", "semantic", "meta"}
)


class TemporalRecord(BaseModel):
    """双时态戳记忆记录

    [v10-ready] 记录同时携带事件时态（event_time）与记录时态（record_time），
    并通过 valid_from/valid_to 表达知识的有效窗口，支持时间旅行查询。
    """

    # 身份
    record_id: str = Field(default_factory=lambda: str(uuid4()))

    # 内容
    content: str
    layer: str  # sensory/working/short_term/episodic/semantic/meta
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # 双时态戳
    event_time: datetime = Field(default_factory=datetime.now)  # 事件实际发生时间
    record_time: datetime = Field(default_factory=datetime.now)  # 系统记录时间
    valid_from: datetime = Field(default_factory=datetime.now)  # 知识有效起始
    valid_to: datetime | None = None  # 知识有效截止（None=当前有效）

    # 版本链
    superseded_by: str | None = None  # 替代本条的新记录ID
    supersedes: str | None = None  # 本条替代的旧记录ID

    # 置信度与来源
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: str = "user"  # user/system/deepseek/consolidation

    # 状态
    is_valid: bool = True  # valid_to is None or valid_to > now
    invalidation_reason: str | None = None

    @model_validator(mode="after")
    def _sync_validity_flag(self) -> "TemporalRecord":
        """根据 valid_to 自动同步 is_valid 状态标志。

        Returns:
            TemporalRecord: 状态标志已同步的本记录实例。
        """
        if self.valid_to is None:
            self.is_valid = True
        else:
            self.is_valid = self.valid_to > datetime.now()
        return self

    def active_at(self, point_in_time: datetime) -> bool:
        """判断记录在指定时间点是否处于有效窗口内。

        Args:
            point_in_time: 待检查的时间点。

        Returns:
            bool: valid_from <= t 且 (valid_to 为空 或 valid_to > t) 时为 True。
        """
        if self.valid_from > point_in_time:
            return False
        return self.valid_to is None or self.valid_to > point_in_time


class TemporalRecordValidator:
    """验证TemporalRecord的时序逻辑一致性

    [v10-ready] 提供时态一致性、版本链完整性与冲突检测三类静态校验。
    """

    @staticmethod
    def validate_temporal_consistency(record: TemporalRecord) -> tuple[bool, str]:
        """检查: valid_from < valid_to, event_time <= record_time 等。

        Args:
            record: 待校验的时序记录。

        Returns:
            tuple[bool, str]: (是否通过, 失败原因)；通过时原因为空字符串。
        """
        if record.layer not in _VALID_LAYERS:
            return False, f"非法层级: {record.layer}"
        if record.event_time > record.record_time:
            return False, "event_time 不应晚于 record_time"
        if record.valid_to is not None and record.valid_from >= record.valid_to:
            return False, "valid_from 必须早于 valid_to"
        if record.superseded_by is not None and record.superseded_by == record.record_id:
            return False, "superseded_by 不能指向自身"
        if record.supersedes is not None and record.supersedes == record.record_id:
            return False, "supersedes 不能指向自身"
        return True, ""

    @staticmethod
    def validate_version_chain(records: list[TemporalRecord]) -> tuple[bool, list[str]]:
        """检查版本链的完整性（无环、无断链）。

        Args:
            records: 同一主题的版本链记录集合。

        Returns:
            tuple[bool, list[str]]: (是否完整, 问题描述列表)。
        """
        issues: list[str] = []
        by_id = {r.record_id: r for r in records}

        TemporalRecordValidator._check_dangling_links(records, by_id, issues)
        TemporalRecordValidator._check_chain_cycle(records, by_id, issues)

        return len(issues) == 0, issues

    @staticmethod
    def _check_dangling_links(
        records: list[TemporalRecord],
        by_id: dict[str, TemporalRecord],
        issues: list[str],
    ) -> None:
        """检测版本链中指向不存在记录的断链。"""
        for record in records:
            target = record.superseded_by
            if target is not None and target not in by_id:
                issues.append(f"断链: {record.record_id} 的 superseded_by={target} 不存在")
            prev = record.supersedes
            if prev is not None and prev not in by_id:
                issues.append(f"断链: {record.record_id} 的 supersedes={prev} 不存在")

    @staticmethod
    def _check_chain_cycle(
        records: list[TemporalRecord],
        by_id: dict[str, TemporalRecord],
        issues: list[str],
    ) -> None:
        """沿 superseded_by 方向遍历，检测版本链中的环。"""
        for record in records:
            visited: set[str] = set()
            cursor: str | None = record.record_id
            while cursor is not None and cursor in by_id:
                if cursor in visited:
                    issues.append(f"成环: 版本链在 {cursor} 处出现循环")
                    break
                visited.add(cursor)
                cursor = by_id[cursor].superseded_by

    @staticmethod
    def detect_conflicts(a: TemporalRecord, b: TemporalRecord) -> bool:
        """检测两条记录是否时间冲突（同一主题、重叠有效窗口）。

        Args:
            a: 第一条记录。
            b: 第二条记录。

        Returns:
            bool: 主题相同且有效窗口重叠且无版本继承关系时为 True。
        """
        if a.record_id == b.record_id:
            return False
        # 已存在版本继承关系的记录不视为冲突
        if a.superseded_by == b.record_id or b.superseded_by == a.record_id:
            return False
        if not TemporalRecordValidator._same_topic(a, b):
            return False
        return TemporalRecordValidator._windows_overlap(a, b)

    @staticmethod
    def _same_topic(a: TemporalRecord, b: TemporalRecord) -> bool:
        """判断两条记录是否属于同一主题（层级相同且标签存在交集）。"""
        if a.layer != b.layer:
            return False
        return bool(set(a.tags) & set(b.tags))

    @staticmethod
    def _windows_overlap(a: TemporalRecord, b: TemporalRecord) -> bool:
        """判断两条记录的有效窗口是否存在时间重叠。"""
        a_end = a.valid_to if a.valid_to is not None else datetime.max
        b_end = b.valid_to if b.valid_to is not None else datetime.max
        return a.valid_from < b_end and b.valid_from < a_end


class TemporalQueryBuilder:
    """构造时间范围查询条件

    [v10-ready] 以链式调用累积过滤条件，实现对时序记录集合的时间旅行查询。
    """

    def __init__(self) -> None:
        """初始化空的过滤条件链。"""
        self._filters: list[Callable[[TemporalRecord], bool]] = []
        self._include_superseded: bool = False

    def as_of(self, point_in_time: datetime) -> "TemporalQueryBuilder":
        """查询在指定时间点有效的记录。

        条件: valid_from <= point_in_time AND (valid_to is None OR valid_to > point_in_time)

        Args:
            point_in_time: 目标时间点。

        Returns:
            TemporalQueryBuilder: 支持链式调用的自身实例。
        """
        self._filters.append(lambda r: r.active_at(point_in_time))
        return self

    def between(self, start: datetime, end: datetime) -> "TemporalQueryBuilder":
        """查询在时间范围内有效的记录（有效窗口与 [start, end] 存在交集）。

        Args:
            start: 范围起点。
            end: 范围终点。

        Returns:
            TemporalQueryBuilder: 支持链式调用的自身实例。
        """

        def _overlap(r: TemporalRecord) -> bool:
            r_end = r.valid_to if r.valid_to is not None else datetime.max
            return r.valid_from < end and start < r_end

        self._filters.append(_overlap)
        return self

    def current_only(self) -> "TemporalQueryBuilder":
        """仅当前有效（valid_to is None）。

        Returns:
            TemporalQueryBuilder: 支持链式调用的自身实例。
        """
        self._filters.append(lambda r: r.valid_to is None)
        return self

    def include_superseded(self) -> "TemporalQueryBuilder":
        """包含已被替代的历史版本。

        Returns:
            TemporalQueryBuilder: 支持链式调用的自身实例。
        """
        self._include_superseded = True
        return self

    def filter(self, records: list[TemporalRecord]) -> list[TemporalRecord]:
        """应用所有条件过滤。

        Args:
            records: 待过滤的时序记录集合。

        Returns:
            list[TemporalRecord]: 满足全部条件的记录列表。
        """
        result: list[TemporalRecord] = []
        for record in records:
            if not self._include_superseded and record.superseded_by is not None:
                continue
            if all(predicate(record) for predicate in self._filters):
                result.append(record)
        return result


def invalidate_record(
    record: TemporalRecord,
    reason: str,
    superseded_by: str | None = None,
) -> TemporalRecord:
    """标记记录失效，返回更新后的记录。

    [v10-ready] 将 valid_to 设为当前时间并写入失效原因，可选地链接替代记录。

    Args:
        record: 待失效的记录。
        reason: 失效原因。
        superseded_by: 替代本条的新记录ID（可选）。

    Returns:
        TemporalRecord: 已标记失效的新记录副本（不修改原记录）。
    """
    now = datetime.now()
    return record.model_copy(
        update={
            "valid_to": now,
            "is_valid": False,
            "invalidation_reason": reason,
            "superseded_by": superseded_by,
        }
    )


def create_temporal_record(content: str, layer: str, **kwargs: Any) -> TemporalRecord:
    """工厂函数：创建新的时序记录。

    [v10-ready] 未显式提供 event_time 时默认等于 record_time。

    Args:
        content: 记忆内容。
        layer: 记忆层级（sensory/working/short_term/episodic/semantic/meta）。
        **kwargs: 透传给 TemporalRecord 的其他字段。

    Returns:
        TemporalRecord: 新建的时序记录实例。
    """
    if "event_time" not in kwargs:
        kwargs["event_time"] = kwargs.get("record_time", datetime.now())
    return TemporalRecord(content=content, layer=layer, **kwargs)
