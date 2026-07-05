# -*- coding: utf-8-sig -*-
"""天机v10.0.1 三重绑定一致性验证策略  [v10-ready]

ConsistencyStrategy — 实现 IValidationStrategy 协议的一致性校验：
    - validate_entry():     检验单条目的引用完整性
                            (标签→条目 / 图谱→条目 / 层级→条目)
    - validate_integrity(): 全局一致性扫描 (悬挂引用/断裂引用/层级/版本链)

提取/参考来源:
    core/consistency_guardian.py 的 ConsistencyGuardian
        verify_references / verify_layer_consistency / verify_version_chain
        (三重绑定: memory_id ↔ asset_id ↔ content_hash 与跨条目引用一致性)

设计差异:
    原 ConsistencyGuardian 直接读取 registry 的 SQLite，
    本策略面向 IValidationStrategy 的 dict 条目接口，
    在内存条目集合上完成等价的引用/层级/版本一致性校验，
    不依赖具体存储后端，便于单进程与分布式统一编程。

架构定位: core/validation/ — 序列化/验证策略插件化子包 (单进程默认实现)
版本: 1.0.0
"""
from __future__ import annotations

from typing import Any

from core.shared.plugin_interface import PluginInfo

# 插件元信息  [v10-ready]
PLUGIN_INFO = PluginInfo(
    name="consistency_checker",
    version="1.0.0",
    description="三重绑定一致性验证策略",
    category="validation",
    protocols=["IValidationStrategy"],
)

# ICME 六层合法层级标识  [v10-ready]
_VALID_LAYERS = frozenset(
    {"sensory", "working", "short_term", "episodic", "semantic", "meta"}
)

# 悬挂引用前缀标记 (沿用 consistency_guardian 约定)  [v10-ready]
_DANGLING_PREFIX = "DANGLING:"


class ConsistencyStrategy:
    """三重绑定一致性验证策略 (实现 IValidationStrategy)  [v10-ready]

    校验记忆条目间的引用完整性与三重绑定一致性：
        - 标签→条目: tags 字段结构合法 (字符串列表)
        - 图谱→条目: references_ids / referenced_by_ids 指向存在的条目
        - 层级→条目: layer 属于 ICME 六层
        - 版本链:     parent_version_id 指向存在的条目

    单条目校验仅做自洽性检查 (字段结构 + 层级 + 悬挂标记)，
    跨条目引用是否断裂需通过 validate_integrity 在全集上扫描。

    本地实现: 单进程默认。
    远程对应: RemoteValidationStrategy (灵境集中式验证服务)。
    """

    def validate_entry(self, entry: dict[str, Any]) -> tuple[bool, str]:
        """检验单条目的引用完整性 (自洽性)。  [v10-ready]

        在不依赖其他条目的前提下，检查本条目的引用相关字段结构是否合法：
            - tags 必须为字符串列表 (标签→条目绑定结构)
            - references_ids / referenced_by_ids 必须为字符串列表 (图谱→条目)
            - 引用项不得携带悬挂标记 DANGLING:
            - layer 若存在必须属于 ICME 六层 (层级→条目)

        Args:
            entry: 待校验的记忆条目字典。

        Returns:
            (是否通过, 原因)；通过时原因为 "ok"。
        """
        if not isinstance(entry, dict):
            return False, f"条目必须为 dict, 实际为 {type(entry).__name__}"

        # 标签→条目: tags 结构合法性
        tags = entry.get("tags", [])
        if tags is not None and not self._is_str_list(tags):
            return False, "字段 tags 必须为字符串列表"

        # 图谱→条目: 引用字段结构与悬挂标记
        for ref_field in ("references_ids", "referenced_by_ids"):
            refs = entry.get(ref_field, [])
            if refs is None:
                continue
            if not self._is_str_list(refs):
                return False, f"字段 {ref_field} 必须为字符串列表"
            for ref_id in refs:
                if ref_id.startswith(_DANGLING_PREFIX):
                    return False, f"{ref_field} 存在悬挂引用: {ref_id}"

        # 层级→条目: layer 合法性
        layer = entry.get("layer")
        if layer is not None and layer not in _VALID_LAYERS:
            return False, f"非法层级: {layer}"

        return True, "ok"

    def validate_integrity(self, entries: list[dict[str, Any]]) -> dict[str, Any]:
        """全局一致性扫描。  [v10-ready]

        在条目全集上执行跨条目一致性校验，等价于
        ConsistencyGuardian 的 verify_references / verify_layer_consistency /
        verify_version_chain 三类检查的内存版本：

            - dangling_reference:   引用携带 DANGLING: 标记
            - broken_reference:     references_ids 指向不存在的条目
            - broken_referenced_by: referenced_by_ids 指向不存在的条目
            - invalid_layer:        layer 不属于 ICME 六层
            - broken_version_chain: parent_version_id 指向不存在的条目

        Args:
            entries: 记忆条目字典列表。

        Returns:
            一致性报告字典，含 total_checked / passed / issues_found /
            issues(详情列表) 等字段。
        """
        valid_entries = [e for e in entries if isinstance(e, dict)]
        known_ids = {
            e["id"] for e in valid_entries if isinstance(e.get("id"), str)
        }
        issues: list[dict[str, Any]] = []

        for entry in valid_entries:
            entry_id = entry.get("id", "<unknown>")

            # 引用一致性 (references_ids)
            for ref_id in self._as_str_list(entry.get("references_ids")):
                if ref_id.startswith(_DANGLING_PREFIX):
                    issues.append(
                        {
                            "type": "dangling_reference",
                            "entry_id": entry_id,
                            "reference": ref_id,
                            "detail": f"条目 {entry_id} 含悬挂引用 {ref_id}",
                        }
                    )
                elif ref_id not in known_ids:
                    issues.append(
                        {
                            "type": "broken_reference",
                            "entry_id": entry_id,
                            "reference": ref_id,
                            "detail": f"条目 {entry_id} 引用了不存在的 {ref_id}",
                        }
                    )

            # 反向引用一致性 (referenced_by_ids)
            for ref_id in self._as_str_list(entry.get("referenced_by_ids")):
                if ref_id.startswith(_DANGLING_PREFIX):
                    continue
                if ref_id not in known_ids:
                    issues.append(
                        {
                            "type": "broken_referenced_by",
                            "entry_id": entry_id,
                            "referenced_by": ref_id,
                            "detail": f"条目 {entry_id} 被不存在的 {ref_id} 引用",
                        }
                    )

            # 层级一致性
            layer = entry.get("layer")
            if layer is not None and layer not in _VALID_LAYERS:
                issues.append(
                    {
                        "type": "invalid_layer",
                        "entry_id": entry_id,
                        "layer": layer,
                    }
                )

            # 版本链一致性
            parent_id = entry.get("parent_version_id")
            if parent_id and parent_id not in known_ids:
                issues.append(
                    {
                        "type": "broken_version_chain",
                        "entry_id": entry_id,
                        "parent_version_id": parent_id,
                        "detail": f"父版本 {parent_id} 不存在",
                    }
                )

        total = len(valid_entries)
        issues_found = len(issues)
        return {
            "strategy": "consistency_checker",
            "total_checked": total,
            "issues_found": issues_found,
            "passed": issues_found == 0,
            "issues": issues,
        }

    @staticmethod
    def _is_str_list(value: Any) -> bool:
        """判定 value 是否为字符串列表。  [v10-ready]

        Args:
            value: 待判定对象。

        Returns:
            为 list 且元素全部为 str 时返回 True。
        """
        return isinstance(value, list) and all(isinstance(x, str) for x in value)

    @staticmethod
    def _as_str_list(value: Any) -> list[str]:
        """安全地将字段规整为字符串列表。  [v10-ready]

        Args:
            value: 原始字段值 (可能为 None / 非列表)。

        Returns:
            仅含字符串元素的列表；非法输入返回空列表。
        """
        if not isinstance(value, list):
            return []
        return [x for x in value if isinstance(x, str)]
