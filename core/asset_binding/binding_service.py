# -*- coding: utf-8-sig -*-
"""L-Asset三重绑定统一服务 (本地实现)  [v10-ready]

AssetBindingService —— 在 AssetAtom / AssetRegistry / AssetSnapshotManager
之上，统一编排 L-Asset 的三重绑定关系，对外提供单一入口:

    - 绑定1: memory_id ↔ asset_id ID映射
    - 绑定2: asset.layer = memory.layer 同层约束
    - 绑定3: version + parent_version_id 版本链 DAG拓扑

设计原则:
    - 不修改 core/asset_atom.py，仅包装/委托其公开 API。
    - 注入 AssetRegistry 时使用 SQLite 持久化；未注入时退化为内存 dict 模式
      (可独立测试，无需数据库)。

实现协议: core.asset_binding.binding_protocol.IAssetBindingService
架构定位: core/asset_binding/ L-Asset绑定层 (本地实现)
版本: 1.0.0
"""
from __future__ import annotations

import logging
import time
from typing import Any

from core.memory.asset_atom import (
    AssetAtom,
    AssetRegistry,
    AssetSnapshotManager,
    AssetStatus,
    ContentType,
    Provenance,
)
from core.shared.plugin_interface import PluginInfo
from core.shared.protocols import MemoryLayer

logger = logging.getLogger("tianji.asset_binding.service")

# 合法记忆层级集合 (绑定2校验依据)
_VALID_LAYERS: frozenset[str] = frozenset(m.value for m in MemoryLayer)


class AssetBindingService:
    """L-Asset三重绑定统一服务  [v10-ready]

    统一管理:
    - 绑定1: memory_id ↔ asset_id 映射
    - 绑定2: asset.layer = memory.layer 同层约束
    - 绑定3: version + parent_version_id DAG拓扑

    委托给现有 AssetRegistry / AssetSnapshotManager 完成底层存储；
    无 Registry 时使用内存 dict 模拟，可独立测试。
    """

    def __init__(
        self,
        registry: AssetRegistry | None = None,
        snapshot_manager: AssetSnapshotManager | None = None,
    ) -> None:
        """初始化绑定服务。  [v10-ready]

        Args:
            registry: 可选 AssetRegistry (SQLite backend)；None 时启用内存模式。
            snapshot_manager: 可选 AssetSnapshotManager (版本快照)。
        """
        self._registry = registry
        self._snapshot_manager = snapshot_manager
        # 内存模式存储: asset_id -> AssetAtom
        self._mem_assets: dict[str, AssetAtom] = {}
        # 绑定1辅助索引: memory_id -> [asset_id, ...]
        self._memory_index: dict[str, list[str]] = {}
        # 已知合法 memory_id 集合 (内存模式下用于判定绑定1是否有效)
        self._known_memories: set[str] = set()
        # 序列计数器 (内存模式生成 asset_id 用)
        self._seq: int = 0
        self._in_memory = registry is None

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _get_atom(self, asset_id: str) -> AssetAtom | None:
        """读取资产原子 (兼容 Registry / 内存模式)。  [v10-ready]"""
        if self._in_memory:
            return self._mem_assets.get(asset_id)
        return self._registry.get(asset_id)

    def _save_atom(self, atom: AssetAtom) -> None:
        """持久化资产原子更新 (兼容 Registry / 内存模式)。  [v10-ready]"""
        atom.updated_at = time.time()
        if self._in_memory:
            self._mem_assets[atom.asset_id] = atom
        else:
            self._registry.update(atom)

    @staticmethod
    def _status_value(status: Any) -> str:
        """归一化 status 为字符串值。  [v10-ready]"""
        return status if isinstance(status, str) else status.value

    @staticmethod
    def _layer_value(entry: dict) -> str:
        """从记忆条目提取层级值，缺省 working。  [v10-ready]"""
        layer = entry.get("layer", MemoryLayer.WORKING.value)
        if isinstance(layer, MemoryLayer):
            return layer.value
        return str(layer)

    # ------------------------------------------------------------------
    # 绑定1: memory_id ↔ asset_id ID映射
    # ------------------------------------------------------------------

    def bind_memory_asset(self, memory_id: str, entry: dict) -> AssetAtom:
        """创建资产并绑定到记忆条目（绑定1: ID映射）。  [v10-ready]

        步骤:
            1. 计算 content_hash 并生成 asset_id
            2. 创建 AssetAtom (layer 与 entry 一致)
            3. 建立 memory_id ↔ asset_id 映射
            4. 注册到 Registry (或内存)

        Args:
            memory_id: 关联的记忆条目标识。
            entry: 记忆条目字典 (含 content/layer/content_type 等)。

        Returns:
            创建并注册后的 AssetAtom。
        """
        content = str(entry.get("content", ""))
        layer = self._layer_value(entry)
        content_type = entry.get("content_type", ContentType.UNKNOWN)
        content_hash = AssetRegistry.compute_content_hash(content)

        # 记录已知记忆 (绑定1有效性判定依据)
        self._known_memories.add(memory_id)

        provenance = Provenance(
            created_by=str(entry.get("created_by", "asset_binding_service")),
            created_at=time.time(),
            reason=str(entry.get("reason", "bind_memory_asset")),
            session_id=str(entry.get("session_id", "")),
        )

        if self._in_memory:
            self._seq += 1
            existing = self._memory_index.get(memory_id, [])
            version = len(existing) + 1
            asset_id = AssetRegistry.generate_asset_id(layer, content_hash, self._seq)
            parent_version_id = existing[-1] if existing else ""
            atom = AssetAtom(
                asset_id=asset_id,
                memory_id=memory_id,
                layer=layer,
                content_type=content_type,
                content_hash=content_hash,
                version=version,
                parent_version_id=parent_version_id,
                provenance=provenance,
                status=AssetStatus.ACTIVE.value,
            )
            # 旧版本标记 superseded
            if parent_version_id and parent_version_id in self._mem_assets:
                prev = self._mem_assets[parent_version_id]
                prev.status = AssetStatus.SUPERSEDED.value
                if asset_id not in prev.referenced_by:
                    prev.referenced_by.append(asset_id)
            self._mem_assets[asset_id] = atom
            self._memory_index.setdefault(memory_id, []).append(asset_id)
        else:
            atom = AssetAtom(
                memory_id=memory_id,
                layer=layer,
                content_type=content_type,
                content_hash=content_hash,
                provenance=provenance,
                status=AssetStatus.ACTIVE.value,
            )
            # Registry.register 在 asset_id 为空时自动生成 id/version/parent
            self._registry.register(atom, content=content)
            self._memory_index.setdefault(memory_id, []).append(atom.asset_id)

        logger.debug(
            "bind_memory_asset: memory_id=%s -> asset_id=%s (layer=%s, v%d)",
            memory_id,
            atom.asset_id,
            atom.layer,
            atom.version,
        )
        return atom

    # ------------------------------------------------------------------
    # 绑定2: 层级标识
    # ------------------------------------------------------------------

    def bind_layer(self, asset_id: str, target_layer: str) -> bool:
        """跨层绑定/重绑定（绑定2: 层级标识）。  [v10-ready]

        步骤:
            1. 查找资产
            2. 验证 target_layer 合法
            3. 更新 layer 字段
            4. 记录 layer 变更历史 (change_log，仅 Registry 模式)

        Args:
            asset_id: 资产唯一标识。
            target_layer: 目标记忆层级。

        Returns:
            绑定是否成功。
        """
        if target_layer not in _VALID_LAYERS:
            logger.warning("bind_layer: 非法层级 %s", target_layer)
            return False

        atom = self._get_atom(asset_id)
        if atom is None:
            logger.warning("bind_layer: 资产不存在 %s", asset_id)
            return False

        old_layer = atom.layer
        if old_layer == target_layer:
            return True

        atom.layer = target_layer
        self._save_atom(atom)

        # 记录层级变更历史 (Registry 模式可用 change_log)
        if not self._in_memory:
            try:
                from core.memory.asset_atom import ChangeAtom

                self._registry.log_change(
                    ChangeAtom(
                        change_type="layer_rebind",
                        target_asset_id=asset_id,
                        diff_summary=f"layer: {old_layer}->{target_layer}",
                        trigger_source="asset_binding_service",
                    )
                )
            except Exception as exc:  # 历史记录失败不影响主流程
                logger.debug("bind_layer: change_log 记录失败 %s", exc)

        logger.debug("bind_layer: %s layer %s->%s", asset_id, old_layer, target_layer)
        return True

    # ------------------------------------------------------------------
    # 绑定3: 版本链 DAG
    # ------------------------------------------------------------------

    def bind_version_chain(self, asset_id: str, parent_id: str) -> bool:
        """建立版本链关系（绑定3: 版本DAG）。  [v10-ready]

        步骤:
            1. 验证 parent 存在
            2. 设置 parent_version_id
            3. 在 parent 的 referenced_by 中添加当前 asset
            4. 版本号基于 parent 自增

        Args:
            asset_id: 当前资产标识。
            parent_id: 父版本资产标识。

        Returns:
            版本链建立是否成功。
        """
        if asset_id == parent_id:
            logger.warning("bind_version_chain: 不能将自身作为父版本 %s", asset_id)
            return False

        atom = self._get_atom(asset_id)
        parent = self._get_atom(parent_id)
        if atom is None or parent is None:
            logger.warning(
                "bind_version_chain: 资产或父版本不存在 asset=%s parent=%s",
                asset_id,
                parent_id,
            )
            return False

        atom.parent_version_id = parent_id
        atom.version = parent.version + 1
        if asset_id not in parent.referenced_by:
            parent.referenced_by.append(asset_id)
        if parent_id not in atom.references:
            atom.references.append(parent_id)

        self._save_atom(parent)
        self._save_atom(atom)

        logger.debug(
            "bind_version_chain: %s <- parent %s (v%d)",
            asset_id,
            parent_id,
            atom.version,
        )
        return True

    # ------------------------------------------------------------------
    # 三重绑定校验
    # ------------------------------------------------------------------

    def verify_triple_binding(self, asset_id: str) -> dict:
        """验证三重绑定完整性。  [v10-ready]

        Args:
            asset_id: 资产唯一标识。

        Returns:
            {
                "asset_id": str,
                "binding_1_valid": bool,  # memory_id 映射是否完整
                "binding_2_valid": bool,  # layer 是否合法且一致
                "binding_3_valid": bool,  # version 链是否完整
                "issues": list[str],
                "overall_valid": bool,
            }
        """
        issues: list[str] = []
        atom = self._get_atom(asset_id)
        if atom is None:
            return {
                "asset_id": asset_id,
                "binding_1_valid": False,
                "binding_2_valid": False,
                "binding_3_valid": False,
                "issues": [f"资产不存在: {asset_id}"],
                "overall_valid": False,
            }

        # --- 绑定1: memory_id 映射完整性 ---
        binding_1_valid = True
        if not atom.memory_id:
            binding_1_valid = False
            issues.append("绑定1: memory_id 为空")
        else:
            mapped = self._memory_index.get(atom.memory_id, [])
            if self._in_memory:
                if atom.memory_id not in self._known_memories:
                    binding_1_valid = False
                    issues.append(f"绑定1: memory_id 已删除/未知 ({atom.memory_id})")
                elif asset_id not in mapped:
                    binding_1_valid = False
                    issues.append("绑定1: memory_id↔asset_id 索引缺失")
            else:
                # Registry 模式: 通过 memory_id 反查应能命中本资产
                siblings = self._registry.get_by_memory_id(atom.memory_id)
                if not any(s.asset_id == asset_id for s in siblings):
                    binding_1_valid = False
                    issues.append("绑定1: Registry 中 memory_id 反查不到本资产")

        # --- 绑定2: layer 合法性 ---
        binding_2_valid = True
        if atom.layer not in _VALID_LAYERS:
            binding_2_valid = False
            issues.append(f"绑定2: 非法 layer ({atom.layer})")

        # --- 绑定3: version 链完整性 ---
        binding_3_valid = True
        if atom.parent_version_id:
            parent = self._get_atom(atom.parent_version_id)
            if parent is None:
                binding_3_valid = False
                issues.append(f"绑定3: 父版本不存在 ({atom.parent_version_id})")
            else:
                if parent.version >= atom.version:
                    binding_3_valid = False
                    issues.append(
                        f"绑定3: 版本号未递增 (parent v{parent.version} >= self v{atom.version})"
                    )
                if asset_id not in parent.referenced_by:
                    binding_3_valid = False
                    issues.append("绑定3: 父版本 referenced_by 缺失反向引用")
        else:
            # 无父版本应为初始版本
            if atom.version != 1:
                binding_3_valid = False
                issues.append(f"绑定3: 无父版本但 version={atom.version} (应为1)")

        overall = binding_1_valid and binding_2_valid and binding_3_valid
        return {
            "asset_id": asset_id,
            "binding_1_valid": binding_1_valid,
            "binding_2_valid": binding_2_valid,
            "binding_3_valid": binding_3_valid,
            "issues": issues,
            "overall_valid": overall,
        }

    # ------------------------------------------------------------------
    # 自动修复
    # ------------------------------------------------------------------

    def repair_binding(self, asset_id: str) -> int:
        """自动修复破损绑定。  [v10-ready]

        修复策略:
            - 绑定1: memory_id 对应记忆已删除 -> 标记资产为 orphan (deleted)
            - 绑定2: layer 非法 -> 修正为缺省 working
            - 绑定3: parent_version_id 无效 -> 断开链接并复位 version

        Args:
            asset_id: 资产唯一标识。

        Returns:
            修复的项数。
        """
        atom = self._get_atom(asset_id)
        if atom is None:
            return 0

        repaired = 0
        dirty = False

        # 绑定1修复: 记忆已删除 -> orphan
        if atom.memory_id and self._in_memory:
            if atom.memory_id not in self._known_memories:
                if self._status_value(atom.status) != AssetStatus.DELETED.value:
                    atom.status = AssetStatus.DELETED.value
                    repaired += 1
                    dirty = True
                    logger.info("repair: %s memory已删除 -> 标记orphan(deleted)", asset_id)

        # 绑定2修复: 非法 layer -> working
        if atom.layer not in _VALID_LAYERS:
            atom.layer = MemoryLayer.WORKING.value
            repaired += 1
            dirty = True
            logger.info("repair: %s 非法layer -> working", asset_id)

        # 绑定3修复: 无效 parent -> 断链复位
        if atom.parent_version_id:
            parent = self._get_atom(atom.parent_version_id)
            if parent is None:
                bad_parent = atom.parent_version_id
                if bad_parent in atom.references:
                    atom.references.remove(bad_parent)
                atom.parent_version_id = ""
                atom.version = 1
                repaired += 1
                dirty = True
                logger.info("repair: %s 无效parent -> 断链复位", asset_id)
            elif asset_id not in parent.referenced_by:
                # 补齐父版本缺失的反向引用
                parent.referenced_by.append(asset_id)
                self._save_atom(parent)
                repaired += 1
                logger.info("repair: %s 补齐parent反向引用", asset_id)

        if dirty:
            self._save_atom(atom)

        return repaired

    # ------------------------------------------------------------------
    # 解绑 (soft delete)
    # ------------------------------------------------------------------

    def unbind(self, asset_id: str) -> bool:
        """解绑资产（soft delete）。  [v10-ready]

        将资产状态置为 deleted，并从 memory 索引移除映射，
        不进行物理删除 (符合天机软删除原则)。

        Args:
            asset_id: 资产唯一标识。

        Returns:
            解绑是否成功。
        """
        atom = self._get_atom(asset_id)
        if atom is None:
            return False

        if self._in_memory:
            atom.status = AssetStatus.DELETED.value
            self._save_atom(atom)
        else:
            current = self._status_value(atom.status)
            # 走状态机合法转移; 非 active 时直接置 deleted 兜底
            ok, _msg = self._registry.transition(
                asset_id, AssetStatus.DELETED.value
            )
            if not ok:
                atom.status = AssetStatus.DELETED.value
                self._registry.update(atom)

        mapped = self._memory_index.get(atom.memory_id)
        if mapped and asset_id in mapped:
            mapped.remove(asset_id)

        logger.debug("unbind: %s -> deleted (soft)", asset_id)
        return True

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------

    def get_binding_stats(self) -> dict:
        """获取绑定统计。  [v10-ready]

        Returns:
            {
                "mode": "memory"|"registry",
                "total_assets": int,
                "bound_memories": int,
                "by_status": dict,
                "by_layer": dict,
            }
        """
        if self._in_memory:
            by_status: dict[str, int] = {}
            by_layer: dict[str, int] = {}
            for atom in self._mem_assets.values():
                st = self._status_value(atom.status)
                by_status[st] = by_status.get(st, 0) + 1
                by_layer[atom.layer] = by_layer.get(atom.layer, 0) + 1
            return {
                "mode": "memory",
                "total_assets": len(self._mem_assets),
                "bound_memories": len(
                    [m for m, ids in self._memory_index.items() if ids]
                ),
                "by_status": by_status,
                "by_layer": by_layer,
            }

        reg_stats = self._registry.get_stats()
        return {
            "mode": "registry",
            "total_assets": reg_stats.get("total_assets", 0),
            "bound_memories": len(
                [m for m, ids in self._memory_index.items() if ids]
            ),
            "by_status": reg_stats.get("by_status", {}),
            "by_layer": reg_stats.get("by_layer", {}),
        }


# 插件元信息  [v10-ready]
PLUGIN_INFO = PluginInfo(
    name="asset_binding_service",
    version="1.0.0",
    description="L-Asset三重绑定统一服务 (本地实现)",
    category="asset_binding",
    protocols=["IAssetBindingService"],
)


__all__ = ["AssetBindingService", "PLUGIN_INFO"]
