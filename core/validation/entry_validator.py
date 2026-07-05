# -*- coding: utf-8-sig -*-
"""天机v10.0.1 记忆条目验证策略  [v10-ready]

EntryValidationStrategy — 实现 IValidationStrategy 协议的本地条目校验：
    - validate_entry():     校验单条记忆的必填字段、字段类型与值范围
    - validate_integrity(): 批量校验并产出统计报告 (通过数/失败数/失败详情)

校验维度:
    1. 必填字段: id / content / layer / timestamp
    2. 字段类型: id/content 为非空字符串, timestamp 为数值或 ISO 字符串
    3. 值范围:   layer 必须属于 ICME 六层枚举, content 长度 >= 最小阈值

架构定位: core/validation/ — 序列化/验证策略插件化子包 (单进程默认实现)
版本: 1.0.0
"""
from __future__ import annotations

from typing import Any

from core.shared.plugin_interface import PluginInfo

# 插件元信息  [v10-ready]
PLUGIN_INFO = PluginInfo(
    name="entry_validator",
    version="1.0.0",
    description="记忆条目验证策略",
    category="validation",
    protocols=["IValidationStrategy"],
)

# ICME 六层合法层级标识  [v10-ready]
_VALID_LAYERS = frozenset(
    {"sensory", "working", "short_term", "episodic", "semantic", "meta"}
)

# 记忆条目必填字段  [v10-ready]
_REQUIRED_FIELDS = ("id", "content", "layer", "timestamp")


class EntryValidationStrategy:
    """记忆条目验证策略 (实现 IValidationStrategy)  [v10-ready]

    进程内条目校验实现，对单条/批量记忆执行结构与取值合法性检查，
    不涉及跨条目引用，仅关注条目自身字段完整性与有效性。

    本地实现: 单进程默认。
    远程对应: RemoteValidationStrategy (灵境集中式验证服务)。
    """

    def __init__(self, *, min_content_length: int = 1) -> None:
        """初始化条目验证策略。

        Args:
            min_content_length: content 字段允许的最小长度 (默认 1)。
        """
        self.min_content_length = min_content_length

    def validate_entry(self, entry: dict[str, Any]) -> tuple[bool, str]:
        """验证单个记忆条目。  [v10-ready]

        依次检查: 类型(必须为 dict) -> 必填字段 -> 字段类型 -> 值范围。
        任一项不通过即短路返回失败原因。

        Args:
            entry: 待校验的记忆条目字典。

        Returns:
            (是否通过, 原因)；通过时原因为 "ok"。
        """
        if not isinstance(entry, dict):
            return False, f"条目必须为 dict, 实际为 {type(entry).__name__}"

        # 1. 必填字段检查
        for fld in _REQUIRED_FIELDS:
            if fld not in entry:
                return False, f"缺失必填字段: {fld}"
            if entry[fld] is None:
                return False, f"必填字段为空: {fld}"

        # 2. 字段类型检查
        if not isinstance(entry["id"], str) or not entry["id"].strip():
            return False, "字段 id 必须为非空字符串"
        if not isinstance(entry["content"], str):
            return False, "字段 content 必须为字符串"
        if not isinstance(entry["layer"], str):
            return False, "字段 layer 必须为字符串"
        if not isinstance(entry["timestamp"], (int, float, str)):
            return False, "字段 timestamp 必须为数值或 ISO 字符串"

        # 3. 值范围检查
        if len(entry["content"]) < self.min_content_length:
            return False, (
                f"content 长度 {len(entry['content'])} 低于最小阈值 "
                f"{self.min_content_length}"
            )
        if entry["layer"] not in _VALID_LAYERS:
            return False, f"非法层级: {entry['layer']}"
        if isinstance(entry["timestamp"], (int, float)) and entry["timestamp"] < 0:
            return False, "timestamp 不能为负数"

        return True, "ok"

    def validate_integrity(self, entries: list[dict[str, Any]]) -> dict[str, Any]:
        """批量完整性验证。  [v10-ready]

        对条目列表逐条调用 validate_entry，汇总通过/失败统计与失败详情。

        Args:
            entries: 记忆条目字典列表。

        Returns:
            验证报告字典，含:
                total / passed / failed / pass_rate / failures(详情列表)。
        """
        total = len(entries)
        passed = 0
        failures: list[dict[str, Any]] = []

        for index, entry in enumerate(entries):
            ok, reason = self.validate_entry(entry)
            if ok:
                passed += 1
            else:
                entry_id = entry.get("id") if isinstance(entry, dict) else None
                failures.append(
                    {
                        "index": index,
                        "id": entry_id,
                        "reason": reason,
                    }
                )

        failed = total - passed
        pass_rate = round(passed / total, 4) if total else 1.0
        return {
            "strategy": "entry_validator",
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": pass_rate,
            "failures": failures,
        }
