r"""
天机国际标准合规 API 路由 (Standards Compliance Routes)
=========================================================
为前端 StandardsCompliance 页面提供真实数据来源。

数据源: core.enforcement.standards_compliance.StandardsComplianceBridge
  - OWASP AOS  : 6类14条安全规则定义 (真实模块加载)
  - MS Agent   : 8 SpanKind + 5 生命周期阶段 + 运行期任务统计
  - OTel Eval  : 6维评分矩阵 + 运行期评估统计

端点:
  GET /api/standards/report  -> 前端 StandardsReport 结构
"""

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

router = APIRouter()


def _build_owasp_section(bridge: Any) -> Dict[str, Any]:
    """组装 OWASP AOS 区块（基于真实规则定义）。"""
    from core.enforcement.standards_compliance import (  # type: ignore[import]
        P15_OWASP_AOS_NEW_RULES,
    )

    coverage = bridge.check_owasp_aos_coverage()
    rules_detail: Dict[str, List[Dict[str, Any]]] = {}
    total_rules = 0
    active_rules = 0
    for category, rules in P15_OWASP_AOS_NEW_RULES.items():
        detail_list: List[Dict[str, Any]] = []
        for rule in rules:
            # 规则一经模块加载即为启用状态
            enabled = True
            detail_list.append(
                {
                    "name": rule.get("name", rule.get("rule_id", "unknown")),
                    "enabled": enabled,
                    "category": category,
                }
            )
            total_rules += 1
            if enabled:
                active_rules += 1
        rules_detail[category] = detail_list

    return {
        "total_rules": total_rules,
        "active_rules": active_rules,
        "categories": coverage.get("total_categories", len(rules_detail)),
        "compliance_rate": float(coverage.get("current_coverage", 100)),
        "rules_detail": rules_detail,
    }


def _build_ms_agent_section(bridge: Any) -> Dict[str, Any]:
    """组装 Microsoft Agent Task 区块（结构定义 + 运行期统计）。"""
    coverage = bridge.get_ms_agent_coverage()
    lifecycle_stats = bridge._lifecycle_manager.get_stats()

    return {
        "span_kinds": len(coverage.get("span_kinds", [])),
        "lifecycle_stages": len(coverage.get("lifecycle_phases", [])),
        "total_tasks": int(lifecycle_stats.get("total_tasks", 0)),
        "completed_tasks": int(lifecycle_stats.get("completed", 0)),
        "failed_tasks": int(lifecycle_stats.get("failed", 0)),
    }


def _grade_from_score(score: float) -> str:
    """按 OTel GenAI Evaluation 分级阈值映射等级。"""
    if score >= 0.85:
        return "EXCELLENT"
    if score >= 0.70:
        return "GOOD"
    if score >= 0.50:
        return "FAIR"
    return "POOR"


def _build_otel_section(bridge: Any) -> Dict[str, Any]:
    """组装 OTel GenAI Evaluation 区块（维度定义 + 运行期评估统计）。"""
    coverage = bridge.get_otel_eval_coverage()
    eval_stats = bridge._multi_dim_evaluator.get_stats()

    dimensions = coverage.get("dimensions", [])
    evaluations_count = int(eval_stats.get("total", 0))
    avg_score = float(eval_stats.get("avg_overall", 0.0))
    dimension_scores: Dict[str, float] = dict(eval_stats.get("dimension_averages", {}))

    return {
        "dimensions": len(dimensions),
        "evaluations_count": evaluations_count,
        "avg_score": avg_score,
        "grade": _grade_from_score(avg_score) if evaluations_count > 0 else "NO_DATA",
        "dimension_scores": dimension_scores,
    }


@router.get("/report")
async def standards_report() -> Dict[str, Any]:
    """返回国际标准合规报告（前端 StandardsReport 结构，全部为真实数据）。

    Returns:
        Dict[str, Any]: 含 owasp_aos / ms_agent / otel_eval 三个区块。

    Raises:
        HTTPException: 合规模块不可用时返回 500。
    """
    try:
        from core.enforcement.standards_compliance import (  # type: ignore[import]
            StandardsComplianceBridge,
        )

        bridge = StandardsComplianceBridge()
        return {
            "owasp_aos": _build_owasp_section(bridge),
            "ms_agent": _build_ms_agent_section(bridge),
            "otel_eval": _build_otel_section(bridge),
        }
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"标准合规模块加载失败: {exc}",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
