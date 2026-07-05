r"""
资产快照路由 - 策略D混合存储 REST API v1.0
===========================================
提供版本管理、快照查看、内容回滚等端点。

端点列表:
  GET  /api/asset/versions/{memory_id}     — 获取指定记忆的版本链
  GET  /api/asset/content/{memory_id}/{version} — 获取指定版本完整内容
  GET  /api/asset/snapshot/{snapshot_id}   — 获取单个快照详情
  GET  /api/asset/stats/{memory_id}        — 获取记忆的快照统计
  GET  /api/asset/stats                    — 全局快照统计
  POST /api/asset/compare                  — 比较两个版本
  POST /api/asset/rollback                 — 回滚到指定版本
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List

from server.deps import engine

router = APIRouter()


def _get_snapshot_mgr():
    """获取快照管理器实例"""
    if engine is None:
        raise HTTPException(status_code=503, detail="引擎未初始化")
    mgr = getattr(engine, "_snapshot_mgr", None)
    if mgr is None:
        raise HTTPException(status_code=503, detail="快照管理器未初始化（策略D未启用）")
    return mgr


def _get_asset_registry():
    """获取资产注册表实例"""
    if engine is None:
        raise HTTPException(status_code=503, detail="引擎未初始化")
    registry = getattr(engine, "_asset_registry", None)
    if registry is None:
        raise HTTPException(status_code=503, detail="资产注册表未初始化")
    return registry


# ── 请求模型 ──────────────────────────────────────────

class RollbackRequest(BaseModel):
    memory_id: str
    target_version: int
    reason: str = "manual_rollback"


class CompareRequest(BaseModel):
    memory_id: str
    version_a: int
    version_b: int


class SnapshotInfo(BaseModel):
    snapshot_id: str
    asset_id: str
    snapshot_type: str
    base_snapshot_id: str
    size: int
    compressed: bool
    checkpoint: bool
    version: int
    created_at: float


# ── 端点实现 ──────────────────────────────────────────


@router.get("/versions/{memory_id}", response_model=List[SnapshotInfo])
async def get_version_chain(
    memory_id: str,
    max_versions: int = Query(default=50, ge=1, le=200),
):
    """
    获取指定记忆的完整版本链

    返回按版本号倒序排列的快照信息列表：
    - snapshot_type: FULL(全量快照) 或 DIFF(增量diff)
    - checkpoint: 是否是检查点（每10版一个）
    - 包含大小、是否压缩等元信息
    """
    mgr = _get_snapshot_mgr()
    chain = mgr.get_version_chain(memory_id, max_versions=max_versions)
    return chain


@router.get("/content/{memory_id}/{version}")
async def get_version_content(
    memory_id: str,
    version: int,
):
    """
    获取指定版本的完整内容（通过快照链重建）

    重建算法：
    - 如果是FULL快照 → 直接返回
    - 如果是DIFF快照 → 沿快照链递归重建，逐级apply diff直到FULL起点
    - 返回完整内容和版本元信息
    """
    mgr = _get_snapshot_mgr()
    content = mgr.get_content_at_version(memory_id, version)
    if content is None:
        raise HTTPException(status_code=404, detail=f"版本 v{version} 不存在或内容不可重建")

    # 同时获取该版本的快照链信息
    chain = mgr.get_version_chain(memory_id, max_versions=100)
    snap_info = None
    for s in chain:
        if s["version"] == version:
            snap_info = s
            break

    # 计算回滚步骤数
    steps_from_checkpoint = 0
    if snap_info and snap_info["snapshot_type"] == "DIFF":
        checkpoint = mgr.find_nearest_checkpoint(memory_id, version)
        if checkpoint:
            steps_from_checkpoint = version - checkpoint["version"]

    return {
        "memory_id": memory_id,
        "version": version,
        "content": content,
        "snapshot_type": snap_info["snapshot_type"] if snap_info else "unknown",
        "checkpoint": snap_info["checkpoint"] if snap_info else False,
        "steps_from_nearest_checkpoint": steps_from_checkpoint,
    }


@router.get("/snapshot/{snapshot_id}")
async def get_snapshot_detail(snapshot_id: str):
    """获取单个快照的详细信息（不含内容）"""
    mgr = _get_snapshot_mgr()
    conn = mgr._get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM asset_snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"快照 {snapshot_id} 不存在")
        content_blob = row["content"]
        include_content = len(content_blob) < 10240  # 小于10KB才返回内容
        return {
            "snapshot_id": row["snapshot_id"],
            "asset_id": row["asset_id"],
            "memory_id": row["memory_id"],
            "snapshot_type": row["snapshot_type"],
            "base_snapshot_id": row["base_snapshot_id"],
            "size": row["size"],
            "compressed": bool(row["compressed"]),
            "checkpoint": bool(row["checkpoint"]),
            "version": row["version"],
            "tcl_canonical_ids": __import__("json").loads(row["tcl_canonical_ids"]),
            "created_at": row["created_at"],
            "content": (
                content_blob.decode("utf-8") if include_content else "[content too large, use /content endpoint]"
            ),
        }
    finally:
        conn.close()


@router.get("/stats/{memory_id}")
async def get_memory_stats(memory_id: str):
    """获取指定记忆的快照存储统计"""
    mgr = _get_snapshot_mgr()
    stats = mgr.get_snapshot_stats(memory_id)
    return stats


@router.get("/stats")
async def get_global_stats():
    """获取全局快照存储统计"""
    mgr = _get_snapshot_mgr()
    stats = mgr.get_global_stats()
    return stats


@router.post("/compare")
async def compare_versions(req: CompareRequest):
    """
    比较两个版本的差异

    返回unified diff格式的差异内容，
    以及统计信息（新增/删除行数）
    """
    mgr = _get_snapshot_mgr()
    content_a = mgr.get_content_at_version(req.memory_id, req.version_a)
    content_b = mgr.get_content_at_version(req.memory_id, req.version_b)

    if content_a is None:
        raise HTTPException(status_code=404, detail=f"版本 v{req.version_a} 不存在")
    if content_b is None:
        raise HTTPException(status_code=404, detail=f"版本 v{req.version_b} 不存在")

    from core.memory.asset_atom import DiffEngine
    de = DiffEngine()
    diff_text = de.generate(
        content_a, content_b,
        old_label=f"v{req.version_a}",
        new_label=f"v{req.version_b}",
    )
    summary = de.compute_diff_summary(diff_text)

    return {
        "memory_id": req.memory_id,
        "version_a": req.version_a,
        "version_b": req.version_b,
        "diff": diff_text,
        "summary": summary,
    }


@router.post("/rollback")
async def rollback_to_version(req: RollbackRequest):
    """
    回滚到指定版本

    创建一个新版本，内容等于目标版本的完整内容。
    实际上是在快照链中新增一个FULL快照，标记为checkpoint。

    注意：这不会删除中间版本，只是创建一个新版本用于后续编辑。
    """
    mgr = _get_snapshot_mgr()
    content = mgr.get_content_at_version(req.memory_id, req.target_version)
    if content is None:
        raise HTTPException(status_code=404, detail=f"版本 v{req.target_version} 不存在或不可重建")

    registry = _get_asset_registry()

    # 获取当前最新版本信息
    latest_atoms = registry.get_by_memory_id(req.memory_id)
    current_version = max((a.version for a in latest_atoms), default=0)

    new_version = current_version + 1
    content_hash = registry.compute_content_hash(content)

    # 判断内容类型
    from core.memory.asset_atom import AssetAtom, ContentType, Provenance
    content_type = ContentType.FILE
    if latest_atoms:
        content_type = latest_atoms[0].content_type if isinstance(latest_atoms[0].content_type, str) else latest_atoms[0].content_type.value

    # 创建新的AssetAtom
    atom = AssetAtom(
        memory_id=req.memory_id,
        layer=latest_atoms[0].layer if latest_atoms else "working",
        content_type=content_type,
        content_hash=content_hash,
        provenance=Provenance(
            created_by="rollback_api",
            created_at=__import__("time").time(),
            reason=f"Rollback to v{req.target_version}: {req.reason}",
        ),
    )

    # 注册资产 + 存储FULL快照
    asset_id = registry.register(atom, content=content)

    # 获取重建步骤信息
    chain = mgr.get_version_chain(req.memory_id, max_versions=100)
    steps = 0
    for s in chain:
        if s["version"] == req.target_version:
            if s["snapshot_type"] == "DIFF":
                checkpoint = mgr.find_nearest_checkpoint(req.memory_id, req.target_version)
                if checkpoint:
                    steps = req.target_version - checkpoint["version"]
            break

    return {
        "status": "rolled_back",
        "memory_id": req.memory_id,
        "source_version": req.target_version,
        "new_version": new_version,
        "new_asset_id": asset_id,
        "reconstruction_steps": steps,
        "reason": req.reason,
    }
