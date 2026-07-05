# -*- coding: utf-8-sig -*-
"""天机v10.0.1 序列化/验证策略插件化子包 (core/validation/)  [v10-ready]

将序列化/验证逻辑从 agent_serializer / consistency_guardian 中提取并插件化，
统一面向 core.shared.protocols 的策略接口编程：

序列化 (ISerializationStrategy):
    JSONSerializationStrategy   — JSON 序列化 (单进程默认, 支持 datetime/dataclass/enum)
    RemoteSerializationStrategy — 远程二进制序列化 (灵境 stub, v10.0 分布式) [预留]

验证 (IValidationStrategy):
    EntryValidationStrategy     — 记忆条目字段校验 (必填/类型/值范围)
    ConsistencyStrategy         — 三重绑定一致性验证 (引用/层级/版本链)
    RemoteValidationStrategy    — 远程集中式验证 (灵境 stub, v10.0 分布式)

切换方式: 由上层按运行模式选择 Local(JSON/Entry/Consistency) 或 Remote 实现，
上层仅依赖 ISerializationStrategy / IValidationStrategy，无需感知实现位置。

兼容性: 不修改 agent_serializer.py / consistency_guardian.py 原文件与对外接口，
本子包为新增的并行插件化实现，v9.1 现有 import 路径不受影响。

架构定位: core/validation/ — 序列化/验证策略插件化子包
版本: 1.0.0
"""

from __future__ import annotations

from core.validation.consistency_checker import ConsistencyStrategy
from core.validation.entry_validator import EntryValidationStrategy
from core.validation.json_serializer import JSONSerializationStrategy
from core.validation.remote_stub import RemoteValidationStrategy

__all__ = [
    # 序列化策略实现
    "JSONSerializationStrategy",
    # 验证策略实现
    "EntryValidationStrategy",
    "ConsistencyStrategy",
    # 远程实现 (stub)
    "RemoteValidationStrategy",
]
