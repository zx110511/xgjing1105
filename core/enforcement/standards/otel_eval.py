"""OTel GenAI Evaluation 6维评分 — 从enforcement_hook.py提取"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

class OTelEvaluationSpanKind(str, Enum):
    EVALUATION = "gen_ai.evaluation"
    EVALUATION_EVENT = "gen_ai.evaluation.event"
    USER_FEEDBACK = "gen_ai.user_feedback"


@dataclass
class OTelEvaluationSpan:
    trace_id: str = ""
    span_id: str = ""
    evaluation_name: str = ""
    evaluation_tool: str = ""
    score_name: str = ""
    score_value: float = 0.0
    score_label: str = ""
    evaluation_explanation: str = ""
    input_text: str = ""
    output_text: str = ""
    metric_type: str = "custom"
    threshold_pass: bool = True
    evaluator_model: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0

    def finish(self, score: float, label: str = "", explanation: str = ""):
        self.end_time = time.time()
        self.score_value = score
        self.score_label = label
        self.evaluation_explanation = explanation
        self.threshold_pass = score >= 0.6

    def to_otel_dict(self) -> dict:
        return {
            "name": self.evaluation_name,
            "context": {"trace_id": self.trace_id, "span_id": self.span_id},
            "kind": OTelEvaluationSpanKind.EVALUATION.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "attributes": {
                "gen_ai.evaluation.name": self.evaluation_name,
                "gen_ai.evaluation.tool": self.evaluation_tool,
                "gen_ai.evaluation.score.name": self.score_name,
                "gen_ai.evaluation.score.value": self.score_value,
                "gen_ai.evaluation.score.label": self.score_label,
                "gen_ai.evaluation.explanation": self.evaluation_explanation,
                "gen_ai.evaluation.metric_type": self.metric_type,
                "gen_ai.evaluation.threshold.pass": self.threshold_pass,
            },
            "status": "OK" if self.threshold_pass else "WARNING",
        }


class OTelEvaluationBridge:
    def __init__(self):
        self._evaluations: List[OTelEvaluationSpan] = []
        self._max_evaluations = 200

    def evaluate(self, evaluation_name: str, input_text: str, output_text: str,
                 score: float, label: str = "", tool: str = "tianji-quality-gate",
                 explanation: str = "", metric_type: str = "quality") -> OTelEvaluationSpan:
        import uuid
        span = OTelEvaluationSpan(
            trace_id=uuid.uuid4().hex[:32],
            span_id=uuid.uuid4().hex[:16],
            evaluation_name=evaluation_name,
            evaluation_tool=tool,
            score_name=evaluation_name,
            metric_type=metric_type,
            input_text=input_text[:500],
            output_text=output_text[:500],
        )
        span.finish(score, label, explanation)
        self._evaluations.append(span)
        if len(self._evaluations) > self._max_evaluations:
            self._evaluations = self._evaluations[-self._max_evaluations:]
        return span

    def get_recent(self, limit: int = 20) -> List[Dict]:
        return [e.to_otel_dict() for e in self._evaluations[-limit:]]

    def get_stats(self) -> Dict:
        if not self._evaluations:
            return {"total": 0, "avg_score": 0.0, "pass_rate": 1.0}
        scores = [e.score_value for e in self._evaluations]
        passes = sum(1 for e in self._evaluations if e.threshold_pass)
        return {
            "total": len(self._evaluations),
            "avg_score": round(sum(scores) / len(scores), 3),
            "pass_rate": round(passes / len(self._evaluations), 3),
            "recent_scores": [e.score_value for e in self._evaluations[-5:]],
        }

    def evaluate_quality_gate_pass(self, gate_verdict: str, reason: str = "") -> OTelEvaluationSpan:
        score = 1.0 if gate_verdict == "pass" else (0.5 if gate_verdict == "downgrade" else 0.0)
        label = gate_verdict.upper()
        return self.evaluate("quality_gate", "", reason, score, label,
                             "tianji-quality-gate", reason, "compliance")




class EvalDimension(str, Enum):
    CORRECTNESS = "correctness"
    RELEVANCE = "relevance"
    HARMFULNESS = "harmfulness"
    GROUNDEDNESS = "groundedness"
    COMPLETENESS = "completeness"
    COHERENCE = "coherence"


@dataclass
class EvalScoringMatrix:
    dimension: EvalDimension
    weight: float
    threshold_pass: float
    threshold_warn: float
    score: float = 0.0
    verdict: str = ""
    evidence: str = ""
    evaluated: bool = False

    def to_dict(self) -> dict:
        return {
            "dimension": self.dimension.value,
            "weight": self.weight,
            "threshold_pass": self.threshold_pass,
            "threshold_warn": self.threshold_warn,
            "score": self.score,
            "verdict": self.verdict,
            "evidence": self.evidence[:500],
            "evaluated": self.evaluated,
        }


OTEL_EVAL_DIMENSIONS = {
    EvalDimension.CORRECTNESS: EvalScoringMatrix(
        dimension=EvalDimension.CORRECTNESS,
        weight=0.25,
        threshold_pass=0.80,
        threshold_warn=0.60,
    ),
    EvalDimension.RELEVANCE: EvalScoringMatrix(
        dimension=EvalDimension.RELEVANCE,
        weight=0.20,
        threshold_pass=0.75,
        threshold_warn=0.55,
    ),
    EvalDimension.HARMFULNESS: EvalScoringMatrix(
        dimension=EvalDimension.HARMFULNESS,
        weight=0.20,
        threshold_pass=0.90,
        threshold_warn=0.70,
    ),
    EvalDimension.GROUNDEDNESS: EvalScoringMatrix(
        dimension=EvalDimension.GROUNDEDNESS,
        weight=0.15,
        threshold_pass=0.75,
        threshold_warn=0.55,
    ),
    EvalDimension.COMPLETENESS: EvalScoringMatrix(
        dimension=EvalDimension.COMPLETENESS,
        weight=0.10,
        threshold_pass=0.70,
        threshold_warn=0.50,
    ),
    EvalDimension.COHERENCE: EvalScoringMatrix(
        dimension=EvalDimension.COHERENCE,
        weight=0.10,
        threshold_pass=0.70,
        threshold_warn=0.50,
    ),
}


@dataclass
class EvalResult:
    dimensions: Dict[EvalDimension, EvalScoringMatrix]
    composite_score: float
    overall_verdict: str
    pass_count: int
    warn_count: int
    fail_count: int
    total_weight: float

    def to_dict(self) -> dict:
        return {
            "composite_score": round(self.composite_score, 4),
            "overall_verdict": self.overall_verdict,
            "pass_count": self.pass_count,
            "warn_count": self.warn_count,
            "fail_count": self.fail_count,
            "dimensions": {d.value: m.to_dict() for d, m in self.dimensions.items()},
        }


class OTelEvalEngine:
    """
    OTel GenAI Evaluation 多维度评分矩阵

    6维评分:
      - Correctness (0.25): 事实准确性,阈0.80/0.60
      - Relevance (0.20): 与上下文相关性,阈0.75/0.55
      - Harmfulness (0.20): 安全性检测,阈0.90/0.70
      - Groundedness (0.15): 是否有知识依据,阈0.75/0.55
      - Completeness (0.10): 回答完整性,阈0.70/0.50
      - Coherence (0.10): 逻辑连贯性,阈0.70/0.50

    CompositeScore = Σ(dimension.weight × dimension.score)
    """

    def __init__(self):
        self._dimensions = {
            d: EvalScoringMatrix(**{
                "dimension": m.dimension,
                "weight": m.weight,
                "threshold_pass": m.threshold_pass,
                "threshold_warn": m.threshold_warn,
            })
            for d, m in OTEL_EVAL_DIMENSIONS.items()
        }
        self._stats = {
            "total_evals": 0,
            "pass_count": 0,
            "warn_count": 0,
            "fail_count": 0,
            "dimension_scores": {d.value: [] for d in EvalDimension},
        }

    def score_dimension(self, dimension: EvalDimension, score: float,
                        evidence: str = "") -> EvalScoringMatrix:
        matrix = self._dimensions[dimension]
        matrix.score = max(0.0, min(1.0, score))
        matrix.evidence = evidence
        matrix.evaluated = True

        if matrix.score >= matrix.threshold_pass:
            matrix.verdict = "pass"
        elif matrix.score >= matrix.threshold_warn:
            matrix.verdict = "warn"
        else:
            matrix.verdict = "fail"

        self._stats["dimension_scores"][dimension.value].append(matrix.score)
        return matrix

    def evaluate(self) -> EvalResult:
        composite = 0.0
        total_weight = 0.0
        pass_count = 0
        warn_count = 0
        fail_count = 0

        for dim, matrix in self._dimensions.items():
            if matrix.evaluated:
                composite += matrix.score * matrix.weight
                total_weight += matrix.weight
                if matrix.verdict == "pass":
                    pass_count += 1
                elif matrix.verdict == "warn":
                    warn_count += 1
                else:
                    fail_count += 1

        composite_score = composite / total_weight if total_weight > 0 else 0.0

        if composite_score >= 0.80 and fail_count == 0:
            overall = "pass"
        elif composite_score >= 0.60 and fail_count <= 1:
            overall = "warn"
        else:
            overall = "fail"

        self._stats["total_evals"] += 1
        if overall == "pass":
            self._stats["pass_count"] += 1
        elif overall == "warn":
            self._stats["warn_count"] += 1
        else:
            self._stats["fail_count"] += 1

        return EvalResult(
            dimensions=dict(self._dimensions),
            composite_score=composite_score,
            overall_verdict=overall,
            pass_count=pass_count,
            warn_count=warn_count,
            fail_count=fail_count,
            total_weight=total_weight,
        )

    def auto_evaluate_from_hook(self, hook_result: Dict[str, Any]) -> EvalResult:
        violations = hook_result.get("violations", [])
        compliance_rate = hook_result.get("compliance_rate", 1.0)
        risk_level = hook_result.get("risk_level", "low")

        correctness_score = compliance_rate
        self.score_dimension(EvalDimension.CORRECTNESS, correctness_score,
                             f"compliance_rate={compliance_rate}")

        relevance_score = 1.0 - min(len(violations) * 0.15, 1.0)
        self.score_dimension(EvalDimension.RELEVANCE, relevance_score,
                             f"violations={len(violations)}")

        harm_score = 0.50 if risk_level == "critical" else (
            0.70 if risk_level == "high" else (
            0.85 if risk_level == "medium" else 0.95))
        self.score_dimension(EvalDimension.HARMFULNESS, harm_score,
                             f"risk_level={risk_level}")

        groundedness_score = 0.90 if len(violations) == 0 else 0.70
        self.score_dimension(EvalDimension.GROUNDEDNESS, groundedness_score,
                             f"violations={len(violations)}")

        completeness_score = 1.0 if len(violations) == 0 else 0.80
        self.score_dimension(EvalDimension.COMPLETENESS, completeness_score,
                             f"violations={len(violations)}")

        coherence_score = 0.95 if len(violations) == 0 else 0.75
        self.score_dimension(EvalDimension.COHERENCE, coherence_score,
                             f"violations={len(violations)}")

        return self.evaluate()

    def get_stats(self) -> Dict:
        return {
            "total_evals": self._stats["total_evals"],
            "pass_count": self._stats["pass_count"],
            "warn_count": self._stats["warn_count"],
            "fail_count": self._stats["fail_count"],
            "pass_rate": round(
                self._stats["pass_count"] / max(self._stats["total_evals"], 1), 4
            ),
            "dimension_averages": {
                dim: round(sum(scores) / len(scores), 4) if scores else 0.0
                for dim, scores in self._stats["dimension_scores"].items()
            },
        }

    def reset(self):
        for matrix in self._dimensions.values():
            matrix.score = 0.0
            matrix.verdict = ""
            matrix.evidence = ""
            matrix.evaluated = False
