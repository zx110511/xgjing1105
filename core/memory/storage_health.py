# -*- coding: utf-8 -*-
"""storage_health.py — 存储健康监控器 [STO-PHASE-3]

提供:
  - 孤儿文件扫描与清理(GC)
  - SQLite/JSON一致性检查
  - 综合健康评分(health_score)
  - 定时巡检调度

集成点:
  - /api/storage/health → storage_health()端点
  - /api/storage/gc     → storage_gc()端点
  - engine.stats()       → 包含health_score字段
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """单次检查结果"""
    name: str
    status: str  # ok | warning | error | critical
    value: Any = None
    detail: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class OrphanRecord:
    """孤儿文件记录"""
    file_id: str
    layer: str
    file_path: str
    size_bytes: int = 0
    detected_at: float = field(default_factory=time.time)


class StorageHealthMonitor:
    """存储健康监控器

    职责:
    1. 扫描孤儿JSON文件(SQLite中不存在的)
    2. 清理孤儿/临时/废弃文件
    3. 检查SQLite与JSON的一致性
    4. 计算综合健康评分
    """

    def __init__(self, sqlite_store=None, data_path: Path | None = None):
        self._store = sqlite_store
        self._data_path = data_path
        self._last_scan_time: float = 0
        self._last_scan_result: dict | None = None
        self._scan_cache_ttl: float = 300  # 缓存5分钟

    @property
    def data_path(self) -> Path:
        if self._data_path:
            return self._data_path
        if self._store and hasattr(self._store, 'db_path'):
            return self._store.db_path.parent
        return Path("data/.memory")

    # ====================================================================
    # 孤儿扫描
    # ====================================================================

    def scan_orphans(self) -> dict:
        """扫描孤儿JSON文件: 在磁盘上存在但SQLite中没有记录的

        Returns:
            {
                "orphan_count": int,
                "orphans": [OrphanRecord, ...],
                "total_json_files": int,
                "sqlite_record_count": int,
                "scan_duration_ms": float,
                "timestamp": float,
            }
        """
        t0 = time.time()
        result = {
            "orphan_count": 0,
            "orphans": [],
            "total_json_files": 0,
            "sqlite_record_count": 0,
            "scan_duration_ms": 0,
            "timestamp": t0,
        }

        try:
            # 1. 获取SQLite全部ID
            sqlite_ids = set()
            if self._store:
                conn = self._store._get_conn()
                rows = conn.execute("SELECT id, layer FROM memories WHERE archived=0").fetchall()
                for r in rows:
                    sqlite_ids.add(r[0])
                result["sqlite_record_count"] = len(rows)

            # 2. 扫描各层JSON文件
            layer_dirs = ["sensory", "short_term", "episodic", "semantic", "meta"]
            memory_dir = self.data_path

            for layer_name in layer_dirs:
                layer_dir = memory_dir / layer_name
                if not layer_dir.exists():
                    continue
                for f in layer_dir.glob("*.json"):
                    if f.name.endswith(".deprecated") or f.name.endswith(".tmp"):
                        continue
                    result["total_json_files"] += 1
                    entry_id = f.stem
                    if entry_id not in sqlite_ids:
                        result["orphans"].append(OrphanRecord(
                            file_id=entry_id,
                            layer=layer_name,
                            file_path=str(f.relative_to(memory_dir)),
                            size_bytes=f.stat().st_size,
                        ))

            result["orphan_count"] = len(result["orphans"])
        except Exception as e:
            logger.error(f"[StorageHealth] scan_orphans失败: {e}", exc_info=True)
            result["error"] = str(e)

        result["scan_duration_ms"] = round((time.time() - t0) * 1000, 2)
        self._last_scan_time = time.time()
        self._last_scan_result = result
        return result

    # ====================================================================
    # GC清理
    # ====================================================================

    def gc_orphans(self, dry_run: bool = True) -> dict:
        """清理孤儿文件

        Args:
            dry_run: True=仅报告不删除, False=实际删除

        Returns:
            {
                "dry_run": bool,
                "deleted_count": int,
                "freed_bytes": int,
                "deleted": [{"file_id", "layer", "file_path", "size_bytes"}, ...],
                "errors": [...],
                "timestamp": float,
            }
        """
        t0 = time.time()
        scan = self.scan_orphans()
        result = {
            "dry_run": dry_run,
            "deleted_count": 0,
            "freed_bytes": 0,
            "deleted": [],
            "errors": [],
            "timestamp": t0,
        }

        for orphan in scan.get("orphans", []):
            full_path = self.data_path / orphan.file_path
            if dry_run:
                result["deleted"].append({
                    "file_id": orphan.file_id,
                    "layer": orphan.layer,
                    "file_path": orphan.file_path,
                    "size_bytes": orphan.size_bytes,
                })
                result["deleted_count"] += 1
                result["freed_bytes"] += orphan.size_bytes
            else:
                try:
                    full_path.unlink()
                    result["deleted"].append({
                        "file_id": orphan.file_id,
                        "layer": orphan.layer,
                        "file_path": orphan.file_path,
                        "size_bytes": orphan.size_bytes,
                        "deleted": True,
                    })
                    result["deleted_count"] += 1
                    result["freed_bytes"] += orphan.size_bytes
                except Exception as e:
                    result["errors"].append({
                        "file_id": orphan.file_id,
                        "error": str(e),
                    })

        result["duration_ms"] = round((time.time() - t0) * 1000, 2)
        level = "DRY-RUN" if dry_run else "EXECUTED"
        logger.info(
            f"[StorageHealth] GC {level}: deleted={result['deleted_count']} "
            f"freed={result['freed_bytes']/1024:.1f}KB errors={len(result['errors'])}"
        )
        return result

    def gc_deprecated(self, max_age_days: int = 30, dry_run: bool = True) -> dict:
        """清理过期的.deprecated文件(超过兼容期的备份)

        Args:
            max_age_days: deprecated文件保留天数
            dry_run: True=仅报告
        """
        t0 = time.time()
        result = {"dry_run": dry_run, "deleted_count": 0, "freed_bytes": 0, "deleted": [], "errors": []}
        cutoff = time.time() - (max_age_days * 86400)
        memory_dir = self.data_path

        for dep_file in memory_dir.rglob("*.deprecated"):
            try:
                mtime = dep_file.stat().st_mtime
                if mtime < cutoff:
                    if dry_run:
                        result["deleted"].append({"file": str(dep_file.relative_to(memory_dir)), "age_days": round((time.time() - mtime) / 86400, 1)})
                        result["deleted_count"] += 1
                        result["freed_bytes"] += dep_file.stat().st_size
                    else:
                        dep_file.unlink()
                        result["deleted_count"] += 1
            except Exception as e:
                result["errors"].append({"file": str(dep_file), "error": str(e)})

        result["duration_ms"] = round((time.time() - t0) * 1000, 2)
        return result

    # ====================================================================
    # 一致性检查
    # ====================================================================

    def consistency_check(self) -> dict:
        """完整一致性检查报告

        Returns:
            {
                "overall_status": "healthy" | "degraded" | "unhealthy",
                "health_score": float (0-100),
                "checks": {name: HealthCheckResult},
                "summary": str,
                "timestamp": float,
            }
        """
        checks = {}
        t0 = time.time()

        # Check 1: SQLite记录数 vs JSON文件数
        c1 = self._check_record_count_consistency()
        checks["record_count"] = c1

        # Check 2: 孤儿文件检测
        orphans = self.scan_orphans()
        c2 = HealthCheckResult(
            name="orphan_files",
            status="ok" if orphans["orphan_count"] == 0 else ("warning" if orphans["orphan_count"] < 50 else "critical"),
            value=orphans["orphan_count"],
            detail=f"{orphans['orphan_count']}个孤儿文件",
        )
        checks["orphan_files"] = c2

        # Check 3: system_config表状态
        c3 = self._check_system_config()
        checks["system_config"] = c3

        # Check 4: 临时文件残留
        c4 = self._check_temp_files()
        checks["temp_files"] = c4

        # Check 5: 磁盘空间
        c5 = self._check_disk_space()
        checks["disk_space"] = c5

        # 综合评分
        ok_count = sum(1 for c in checks.values() if c.status == "ok")
        total = len(checks)
        health_score = round(ok_count / max(total, 1) * 100, 1)

        if health_score >= 80:
            overall = "healthy"
        elif health_score >= 50:
            overall = "degraded"
        else:
            overall = "unhealthy"

        return {
            "overall_status": overall,
            "health_score": health_score,
            "checks": {k: {"status": v.status, "value": v.value, "detail": v.detail} for k, v in checks.items()},
            "check_details": {k: v for k, v in checks.items()},
            "summary": f"{overall} ({health_score}/100) — {ok_count}/{total}项通过",
            "duration_ms": round((time.time() - t0) * 1000, 2),
            "timestamp": time.time(),
        }

    # ====================================================================
    # 内部检查方法
    # ====================================================================

    def _check_record_count_consistency(self) -> HealthCheckResult:
        """检查SQLite记录数与JSON文件数的偏差"""
        try:
            sqlite_count = 0
            if self._store:
                conn = self._store._get_conn()
                row = conn.execute("SELECT COUNT(*) FROM memories WHERE archived=0").fetchone()
                sqlite_count = row[0] if row else 0

            json_count = 0
            memory_dir = self.data_path
            for ld in ["sensory", "short_term", "episodic", "semantic", "meta"]:
                d = memory_dir / ld
                if d.exists():
                    json_count += len([f for f in d.glob("*.json") if not f.name.endswith((".deprecated", ".tmp"))])

            deviation = abs(sqlite_count - json_count)
            if deviation == 0:
                status = "ok"
            elif deviation < 20:
                status = "warning"
            else:
                status = "critical"

            return HealthCheckResult(
                name="record_count",
                status=status,
                value={"sqlite": sqlite_count, "json": json_count, "deviation": deviation},
                detail=f"SQLite={sqlite_count} JSON={json_count} 偏差={deviation}",
            )
        except Exception as e:
            return HealthCheckResult(name="record_count", status="error", detail=str(e))

    def _check_system_config(self) -> HealthCheckResult:
        """检查system_config表状态"""
        try:
            if self._store and hasattr(self._store, 'config_get_all'):
                configs = self._store.config_get_all()
                expected_keys = {"cognition_state", "llm_stats", "push_cursor", "dashboard_cumulative", "dashboard_history"}
                actual_keys = {c["key"] for c in configs}
                missing = expected_keys - actual_keys
                if missing:
                    return HealthCheckResult(
                        name="system_config",
                        status="warning",
                        value=len(configs),
                        detail=f"缺少配置键: {missing}",
                    )
                return HealthCheckResult(
                    name="system_config",
                    status="ok",
                    value=len(configs),
                    detail=f"{len(configs)}个配置项全部就绪",
                )
            return HealthCheckResult(name="system_config", status="warning", detail="config_get_all不可用")
        except Exception as e:
            return HealthCheckResult(name="system_config", status="error", detail=str(e))

    def _check_temp_files(self) -> HealthCheckResult:
        """检查残留的.tmp临时文件"""
        try:
            tmp_count = 0
            tmp_files = []
            memory_dir = self.data_path
            if memory_dir.exists():
                for tf in memory_dir.rglob("*.json.tmp"):
                    tmp_count += 1
                    tmp_files.append(tf.name)

            if tmp_count == 0:
                return HealthCheckResult(name="temp_files", status="ok", value=0, detail="无残留临时文件")
            return HealthCheckResult(
                name="temp_files",
                status="warning",
                value=tmp_count,
                detail=f"{tmp_count}个残留临时文件: {tmp_files[:5]}",
            )
        except Exception as e:
            return HealthCheckResult(name="temp_files", status="error", detail=str(e))

    def _check_disk_space(self) -> HealthCheckResult:
        """检查磁盘空间"""
        try:
            if hasattr(os, 'statvfs'):
                stat = os.statvfs(str(self.data_path))
                free_mb = stat.f_bavail * stat.f_frsize / (1024 * 1024)
                total_mb = stat.f_blocks * stat.f_frsize / (1024 * 1024)
                if free_mb > 500:
                    status = "ok"
                elif free_mb > 100:
                    status = "warning"
                else:
                    status = "critical"
                return HealthCheckResult(
                    name="disk_space",
                    status=status,
                    value={"free_mb": round(free_mb, 2), "total_mb": round(total_mb, 2)},
                    detail=f"剩余{free_mb:.1f}MB / 总计{total_mb:.1f}MB",
                )
            return HealthCheckResult(name="disk_space", status="ok", detail="跳过(非Unix)")
        except Exception as e:
            return HealthCheckResult(name="disk_space", status="error", detail=str(e))

    # ====================================================================
    # 集成: engine.stats() 补充
    # ====================================================================

    def get_health_stats(self) -> dict:
        """生成可注入engine.stats()的健康统计字典

        返回格式可直接合并到engine.stats()结果中。
        """
        report = self.consistency_check()
        return {
            "health_score": report["health_score"],
            "health_status": report["overall_status"],
            "health_checks_passed": sum(1 for v in report["checks"].values() if v["status"] == "ok"),
            "health_checks_total": len(report["checks"]),
            "orphan_file_count": report["checks"].get("orphan_files", {}).get("value", 0),
            "last_health_check": report["timestamp"],
        }
