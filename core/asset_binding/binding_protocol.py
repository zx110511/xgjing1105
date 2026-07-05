# -*- coding: utf-8-sig -*-
"""L-Asset三重绑定服务协议  [v10-ready]

定义 IAssetBindingService Protocol —— 统一封装 L-Asset 的三重绑定契约:
    - 绑定1: memory_id ↔ asset_id ID映射
    - 绑定2: asset.layer = memory.layer 层级标识
    - 绑定3: version + parent_version_id 版本链 DAG

本地实现: AssetBindingService (core/asset_binding/binding_service.py, 单进程默认)
远程实现: RemoteAssetBinding (core/asset_binding/remote_stub.py, 灵境分布式 stub)

切换方式: 上层仅依赖本 Protocol，由工厂/容器按运行模式返回
Local/Remote 实现，v9.1 单进程运行不受影响，v10.0 分布式可平滑接入。

架构定位: core/asset_binding/ L-Asset绑定层
版本: 1.0.0
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class IAssetBindingService(Protocol):
    """L-Asset三重绑定服务接口  [v10-ready]

    统一管理数字资产原子(AssetAtom)的三重绑定关系，
    委托底层 AssetRegistry / AssetSnapshotManager 完成持久化。
    """

    def bind_memory_asset(self, memory_id: str, entry: dict) -> Any:
        """创建资产并绑定到记忆条目（绑定1: ID映射）。  [v10-ready]

        Args:
            memory_id: 关联的记忆条目标识。
            entry: 记忆条目字典 (含 content/layer/content_type 等)。

        Returns:
            创建的 AssetAtom 实例。
        """
        ...

    def bind_layer(self, asset_id: str, target_layer: str) -> bool:
        """跨层绑定/重绑定（绑定2: 层级标识）。  [v10-ready]

        Args:
            asset_id: 资产唯一标识。
            target_layer: 目标记忆层级。

        Returns:
            绑定是否成功。
        """
        ...

    def bind_version_chain(self, asset_id: str, parent_id: str) -> bool:
        """建立版本链关系（绑定3: 版本DAG）。  [v10-ready]

        Args:
            asset_id: 当前资产标识。
            parent_id: 父版本资产标识。

        Returns:
            版本链建立是否成功。
        """
        ...

    def verify_triple_binding(self, asset_id: str) -> dict:
        """验证三重绑定完整性。  [v10-ready]

        Args:
            asset_id: 资产唯一标识。

        Returns:
            结构化校验结果字典 (含 binding_1/2/3_valid、issues、overall_valid)。
        """
        ...

    def repair_binding(self, asset_id: str) -> int:
        """自动修复破损绑定。  [v10-ready]

        Args:
            asset_id: 资产唯一标识。

        Returns:
            修复的项数。
        """
        ...

    def unbind(self, asset_id: str) -> bool:
        """解绑资产（soft delete）。  [v10-ready]

        Args:
            asset_id: 资产唯一标识。

        Returns:
            解绑是否成功。
        """
        ...

    def get_binding_stats(self) -> dict:
        """获取绑定统计。  [v10-ready]

        Returns:
            绑定统计信息字典。
        """
        ...


__all__ = ["IAssetBindingService"]
