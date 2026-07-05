"""
天机v9.1 鉴衡审计引擎 REST API

Agent: 鉴衡 (@jianheng) — L3 全维审计师
引擎: TianjiAuditEngine v1.0 — 5维 × 4阶段审计流水线

端点:
  POST /api/audit/run          — 触发全量/维度审计
  GET  /api/audit/status       — 最近一次审计结果
  GET  /api/audit/history      — 审计历史列表
  GET  /api/audit/report/{id}  — 单次审计详细报告
  GET  /api/audit/dimensions   — 列出5维能力矩阵
"""

import json
import os
import threading
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/audit", tags=["鉴衡·审计引擎"])

# ═══════════════════════════════════════════════════════════════
# 模型
# ═══════════════════════════════════════════════════════════════


class AuditRunRequest(BaseModel):
    rounds: int = Field(default=1, ge=1, le=10, description="审计轮次")
    skip_dimensions: list[str] = Field(
        default=[],
        description="跳过的维度 (functionality/stability/performance/security/data_accuracy)",
    )
    timeout_seconds: float = Field(default=300.0, description="超时时间(秒)")


class AuditRunResponse(BaseModel):
    success: bool
    audit_id: str
    rounds: int
    dimensions_run: list[str]
    total_checks: int
    total_passed: int
    total_failed: int
    overall_pass_rate: float
    overall_score: float
    overall_max_score: float
    duration_ms: float
    verdict: str
    timestamp: str
    dimensions: dict = Field(default_factory=dict)


class DimensionInfo(BaseModel):
    name: str
    label: str
    weight: float
    description: str
    checks_count: int


# ═══════════════════════════════════════════════════════════════
# 审计引擎包装器 (线程安全)
# ═══════════════════════════════════════════════════════════════


class AuditEngineService:
    """鉴衡审计引擎服务单例"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._history: list[dict] = []
                    cls._instance._last_result: dict | None = None
                    cls._instance._running = False
                    cls._instance._history_dir = (
                        Path(
                            os.environ.get(
                                "AI_MEMORY_ROOT",
                                os.path.join(os.path.dirname(__file__), "..", ".."),
                            )
                        )
                        / "logs"
                        / "audit_reports"
                    )
                    cls._instance._history_dir.mkdir(parents=True, exist_ok=True)
                    cls._instance._load_history()
        return cls._instance

    def _load_history(self):
        """从磁盘加载审计历史"""
        try:
            for f in sorted(self._history_dir.glob("audit-*.json"), reverse=True):
                try:
                    with open(f, encoding="utf-8") as fh:
                        data = json.load(fh)
                        data["_file"] = str(f)
                        self._history.append(data)
                except Exception:
                    pass
            # 同步_last_result: 优先选择有数据的最新审计(跳过空记录)
            for entry in self._history:
                if entry.get("total_checks", 0) > 0 and entry.get("dimensions"):
                    self._last_result = entry
                    break
            # 兜底: 如果所有记录都为空，取最新的
            if not self._last_result and self._history:
                self._last_result = self._history[0]
        except Exception:
            pass

    def run_audit(
        self,
        rounds: int = 1,
        skip_dimensions: list[str] = None,
        timeout_seconds: float = 300.0,
    ) -> dict:
        """执行审计"""
        from core.enforcement.audit_engine import AuditContext, TianjiAuditEngine

        self._running = True
        start = time.time()

        try:
            # [FIX-AUDIT] AuditContext不支持skip_dimensions参数，改为在engine层过滤
            ctx = AuditContext(
                timeout_seconds=timeout_seconds,
            )
            # 通过setattr注入skip_dimensions供engine使用（若engine支持）
            if skip_dimensions:
                try:
                    setattr(ctx, 'skip_dimensions', skip_dimensions)
                except Exception:
                    pass
            engine = TianjiAuditEngine(ctx)
            results = engine.run(rounds=rounds)

            if not results:
                return {"success": False, "error": "Audit precheck failed"}

            final = results[-1]
            dimensions_run = list(final.dimensions.keys())

            audit_id = f"audit-{time.strftime('%Y%m%d-%H%M%S')}"
            duration_ms = (time.time() - start) * 1000

            summary = {
                "success": True,
                "audit_id": audit_id,
                "rounds": rounds,
                "dimensions_run": dimensions_run,
                "total_checks": final.total_checks,
                "total_passed": final.total_passed,
                "total_failed": final.total_failed,
                "overall_pass_rate": round(final.overall_pass_rate, 1),
                "overall_score": round(final.overall_score, 1),
                "overall_max_score": round(final.overall_max_score, 1),
                "duration_ms": round(duration_ms, 0),
                "verdict": "PASS" if final.overall_pass else "FAIL",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }

            # 构建维度详情
            dimensions_detail = {}
            for dn, rp in final.dimensions.items():
                dim = {
                    "dimension": dn,
                    "total_checks": rp.total_checks,
                    "passed": rp.passed,
                    "warned": rp.warned,
                    "failed": rp.failed,
                    "skipped": rp.skipped,
                    "errored": rp.errored,
                    "score": round(rp.score, 1),
                    "max_score": round(rp.max_score, 1),
                    "pass_rate": round(rp.pass_rate, 1),
                    "score_rate": round(rp.score_rate, 1),
                    "checks": [
                        {
                            "check_id": c.check_id,
                            "status": c.status.value,
                            "severity": c.severity.value,
                            "score": c.score,
                            "threshold": c.threshold,
                            "message": c.message,
                            "duration_ms": round(c.duration_ms, 1),
                        }
                        for c in rp.checks
                    ],
                }
                dimensions_detail[dn] = dim

            full_report = {**summary, "dimensions": dimensions_detail}

            # 持久化
            report_file = self._history_dir / f"{audit_id}.json"
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(full_report, f, ensure_ascii=False, indent=2)

            full_report["_file"] = str(report_file)
            self._history.insert(0, full_report)
            self._last_result = full_report

            # 裁剪历史 (保留最近50条)
            if len(self._history) > 50:
                for old in self._history[50:]:
                    try:
                        os.remove(old.get("_file", ""))
                    except Exception:
                        pass
                self._history = self._history[:50]

            return full_report

        except Exception as e:
            import traceback

            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
            }
        finally:
            self._running = False

    def get_status(self) -> dict:
        """获取最近审计状态"""
        if self._last_result:
            return {"running": self._running, "last_audit": self._last_result}
        return {
            "running": self._running,
            "last_audit": None,
            "message": "No audit has been run yet",
        }

    def get_history(self, limit: int = 20) -> list[dict]:
        """获取审计历史"""
        return [
            {k: v for k, v in h.items() if not k.startswith("_")}
            for h in self._history[:limit]
        ]

    def get_report(self, audit_id: str) -> dict | None:
        """获取指定审计报告"""
        for h in self._history:
            if h.get("audit_id") == audit_id:
                return h
        # 尝试从磁盘加载
        report_file = self._history_dir / f"{audit_id}.json"
        if report_file.exists():
            with open(report_file, encoding="utf-8") as f:
                return json.load(f)
        return None


# ═══════════════════════════════════════════════════════════════
# 路由
# ═══════════════════════════════════════════════════════════════


@router.post("/run", response_model=AuditRunResponse)
async def audit_run(request: AuditRunRequest):
    """
    触发鉴衡全维审计

    - 执行 5维 × N轮 审计流水线
    - 支持维度跳过（跳过耗时的性能/稳定维度用于快速检查）
    - 结果自动持久化到 logs/audit_reports/
    """
    svc = AuditEngineService()
    if svc._running:
        raise HTTPException(status_code=409, detail="Audit already running")

    result = svc.run_audit(
        rounds=request.rounds,
        skip_dimensions=request.skip_dimensions,
        timeout_seconds=request.timeout_seconds,
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=500, detail=result.get("error", "Unknown error")
        )

    return result


@router.get("/status")
async def audit_status():
    """获取最近一次审计结果摘要"""
    svc = AuditEngineService()
    return svc.get_status()


@router.get("/history")
async def audit_history(limit: int = Query(default=20, ge=1, le=50)):
    """审计历史列表 (最近N次)"""
    svc = AuditEngineService()
    return {"count": min(limit, len(svc._history)), "history": svc.get_history(limit)}


@router.get("/report/{audit_id}")
async def audit_report(audit_id: str):
    """获取指定审计ID的完整报告"""
    svc = AuditEngineService()
    report = svc.get_report(audit_id)
    if not report:
        raise HTTPException(
            status_code=404, detail=f"Audit report not found: {audit_id}"
        )
    return report


@router.get("/dimensions")
async def audit_dimensions():
    """列出鉴衡5维审计能力矩阵"""
    return {
        "agent": "鉴衡",
        "agent_id": "jianheng",
        "layer": "L3",
        "role": "全维审计师",
        "engine_version": "1.0.0",
        "dimensions": [
            {
                "name": "functionality",
                "label": "功能完整性",
                "weight": 1.5,
                "description": "文件存在性/类可导入性/方法签名/E2E流程 — 系统核心模块是否完整可用",
                "checks_count": 99,
            },
            {
                "name": "stability",
                "label": "系统稳定性",
                "weight": 1.2,
                "description": "重复操作成功率/并发访问/错误恢复/资源清理 — 系统在压力下是否稳定",
                "checks_count": 12,
            },
            {
                "name": "performance",
                "label": "性能指标",
                "weight": 1.0,
                "description": "remember/recall/export 基准延迟/吞吐量/批量性能 — 核心操作是否达标",
                "checks_count": 18,
            },
            {
                "name": "security",
                "label": "安全合规",
                "weight": 1.3,
                "description": "敏感模式检测/危险操作正则/访问控制/密钥扫描 — 是否存在安全隐患",
                "checks_count": 15,
            },
            {
                "name": "data_accuracy",
                "label": "数据准确性",
                "weight": 1.0,
                "description": "哈希一致性/引用完整性/TDAF往返/层完整性 — 数据是否准确可靠",
                "checks_count": 10,
            },
        ],
    }


@router.delete("/history")
async def clear_audit_history():
    """清空审计历史 (软清理，磁盘文件保留)"""
    svc = AuditEngineService()
    svc._history.clear()
    svc._last_result = None
    return {"success": True, "message": "Audit history cleared"}
