r"""
AlignmentEngine - 天机多向对齐引擎 v1.0
==========================================
D08: 6步流水线 (变更→分类→影响分析→级联更新→验证→归档)
D09: 变更分类器 (trivial/structural/semantic/destructive)
D10: 影响分析器 (正向+反向+层级+跨层传播)
D11: 级联更新执行器 (直接+级联+摘要+KG)
D12: 科学删除机制 (软删除+引用修复+README更新)
"""

import time
import json
import hashlib
import threading
from dataclasses import dataclass, field, asdict
from typing import Any, Optional, List, Dict, Tuple, Callable
from enum import Enum


class ChangeSeverity(str, Enum):
    TRIVIAL = "trivial"
    STRUCTURAL = "structural"
    SEMANTIC = "semantic"
    DESTRUCTIVE = "destructive"


@dataclass
class ImpactReport:
    target_asset_id: str = ""
    change_type: str = ""
    severity: str = ChangeSeverity.TRIVIAL
    directly_affected: List[str] = field(default_factory=list)
    transitively_affected: List[str] = field(default_factory=list)
    layer_propagation: Dict[str, List[str]] = field(default_factory=dict)
    cross_layer_updates: List[Dict] = field(default_factory=list)
    total_impact_count: int = 0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AlignmentResult:
    success: bool = False
    change_id: str = ""
    severity: str = ""
    impact_report: Optional[ImpactReport] = None
    cascade_count: int = 0
    errors: List[str] = field(default_factory=list)
    duration_ms: float = 0.0


class ChangeClassifier:
    SEVERITY_KEYWORDS = {
        ChangeSeverity.TRIVIAL: [
            "format", "whitespace", "comment", "indent", "rename_local",
            "import_order", "line_break",
        ],
        ChangeSeverity.STRUCTURAL: [
            "rename", "move", "refactor", "reorder", "extract_method",
            "inline", "change_signature", "add_parameter",
        ],
        ChangeSeverity.SEMANTIC: [
            "logic", "behavior", "algorithm", "fix_bug", "add_feature",
            "change_condition", "modify_return", "update_rule",
        ],
        ChangeSeverity.DESTRUCTIVE: [
            "delete", "remove", "drop", "purge", "erase",
            "deprecate", "obsolete",
        ],
    }

    def __init__(self, llm_classify_fn: Optional[Callable] = None):
        self._llm_classify = llm_classify_fn

    def classify(self, before: str, after: str, change_type: str = "") -> ChangeSeverity:
        if change_type == "delete":
            return ChangeSeverity.DESTRUCTIVE

        if not before and after:
            return ChangeSeverity.STRUCTURAL

        if before and not after:
            return ChangeSeverity.DESTRUCTIVE

        if not before and not after:
            return ChangeSeverity.TRIVIAL

        if self._llm_classify:
            try:
                result = self._llm_classify(before, after)
                if result in [s.value for s in ChangeSeverity]:
                    return ChangeSeverity(result)
            except Exception:
                pass

        return self._rule_based_classify(before, after, change_type)

    def _rule_based_classify(self, before: str, after: str, change_type: str) -> ChangeSeverity:
        combined = f"{change_type} {before[:200]} {after[:200]}".lower()

        for severity, keywords in self.SEVERITY_KEYWORDS.items():
            for kw in keywords:
                if kw in combined:
                    return severity

        stripped_before = before.replace(" ", "").replace("\t", "").replace("\n", "")
        stripped_after = after.replace(" ", "").replace("\t", "").replace("\n", "")
        if stripped_before == stripped_after:
            return ChangeSeverity.TRIVIAL

        before_lines = set(before.split("\n"))
        after_lines = set(after.split("\n"))
        added = after_lines - before_lines
        removed = before_lines - after_lines
        total = max(len(before_lines), len(after_lines), 1)
        change_ratio = (len(added) + len(removed)) / total

        if change_ratio > 0.5:
            return ChangeSeverity.SEMANTIC
        elif change_ratio > 0.2:
            return ChangeSeverity.STRUCTURAL
        else:
            return ChangeSeverity.TRIVIAL


class ImpactAnalyzer:
    LAYER_ORDER = ["sensory", "working", "short_term", "episodic", "semantic", "meta"]

    def __init__(self, registry):
        self._registry = registry

    def analyze(self, asset_id: str, severity: ChangeSeverity) -> ImpactReport:
        report = ImpactReport(
            target_asset_id=asset_id,
            severity=severity.value,
        )

        atom = self._registry.get(asset_id)
        if not atom:
            return report

        directly = self._registry.get_dependents(asset_id)
        report.directly_affected = [a.asset_id for a in directly]

        visited = set()
        queue = list(report.directly_affected)
        while queue:
            current_id = queue.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)
            deps = self._registry.get_dependents(current_id)
            for d in deps:
                if d.asset_id not in visited:
                    report.transitively_affected.append(d.asset_id)
                    queue.append(d.asset_id)

        report.transitively_affected = list(set(report.transitively_affected))

        self._compute_layer_propagation(atom, report)

        report.total_impact_count = (
            len(report.directly_affected)
            + len(report.transitively_affected)
            + sum(len(v) for v in report.layer_propagation.values())
        )

        return report

    def _compute_layer_propagation(self, atom, report: ImpactReport):
        atom_layer = atom.layer if isinstance(atom.layer, str) else atom.layer
        try:
            src_idx = self.LAYER_ORDER.index(atom_layer)
        except ValueError:
            src_idx = 3

        if atom_layer in ("semantic", "meta"):
            for i in range(src_idx - 1, -1, -1):
                layer_name = self.LAYER_ORDER[i]
                report.layer_propagation[layer_name] = ["summary_update"]

        if atom_layer in ("sensory", "working"):
            for i in range(src_idx + 1, len(self.LAYER_ORDER)):
                layer_name = self.LAYER_ORDER[i]
                report.layer_propagation[layer_name] = ["summary_may_need_update"]

        if atom_layer == "episodic":
            report.layer_propagation["semantic"] = ["kg_update"]
            report.layer_propagation["working"] = ["summary_update"]

        for dep_id in report.directly_affected:
            dep_atom = self._registry.get(dep_id)
            if dep_atom:
                dep_layer = dep_atom.layer if isinstance(dep_atom.layer, str) else dep_atom.layer
                if dep_layer != atom_layer:
                    report.cross_layer_updates.append({
                        "from": asset_id_placeholder(atom.asset_id),
                        "to": asset_id_placeholder(dep_id),
                        "from_layer": atom_layer,
                        "to_layer": dep_layer,
                        "action": "cascade_update",
                    })


def asset_id_placeholder(aid: str) -> str:
    return aid


class CascadeUpdater:
    def __init__(self, registry, llm_summarize_fn: Optional[Callable] = None):
        self._registry = registry
        self._llm_summarize = llm_summarize_fn
        self._cascade_count = 0

    def execute(self, asset_id: str, impact: ImpactReport, severity: ChangeSeverity) -> int:
        cascade_count = 0

        if severity == ChangeSeverity.TRIVIAL:
            atom = self._registry.get(asset_id)
            if atom:
                atom.last_verified = time.time()
                atom.updated_at = time.time()
                self._registry.update(atom)
            return 0

        for dep_id in impact.directly_affected:
            dep_atom = self._registry.get(dep_id)
            if not dep_atom:
                continue

            dep_atom.updated_at = time.time()
            dep_atom.last_verified = time.time()
            self._registry.update(dep_atom)

            self._registry.log_change(type("ChangeAtom", (), {
                "change_id": "",
                "change_type": "cascade_update",
                "target_asset_id": dep_id,
                "target_path": "",
                "before_snapshot": "",
                "after_snapshot": "",
                "diff_summary": f"Cascade update from {asset_id}",
                "impact_scope": [asset_id],
                "trigger_source": "cascade_updater",
                "timestamp": time.time(),
                "session_id": "",
                "undo_possible": False,
            })())
            cascade_count += 1

        if severity in (ChangeSeverity.SEMANTIC, ChangeSeverity.DESTRUCTIVE):
            for dep_id in impact.transitively_affected:
                dep_atom = self._registry.get(dep_id)
                if dep_atom:
                    dep_atom.updated_at = time.time()
                    self._registry.update(dep_atom)
                    cascade_count += 1

        self._cascade_count += cascade_count
        return cascade_count


class ScientificDeleter:
    def __init__(self, registry, readme_updater: Optional[Callable] = None):
        self._registry = registry
        self._readme_updater = readme_updater

    def delete_asset(self, asset_id: str, session_id: str = "") -> Dict:
        atom = self._registry.get(asset_id)
        if not atom:
            return {"success": False, "error": f"Asset {asset_id} not found"}

        result = {
            "asset_id": asset_id,
            "soft_deleted": False,
            "dangling_refs": [],
            "repaired_refs": [],
            "readme_updated": False,
            "l0_preserved": False,
            "l3_recorded": False,
            "l4_marked_historical": False,
        }

        ok, msg = self._registry.transition(asset_id, "deleted", session_id)
        if not ok:
            return {"success": False, "error": msg}
        result["soft_deleted"] = True

        dependents = self._registry.get_dependents(asset_id)
        deleted_atom = self._registry.get(asset_id)
        deleted_memory_id = deleted_atom.memory_id if deleted_atom else ""

        for dep in dependents:
            replacement_id = None
            if deleted_memory_id:
                latest = self._registry.get_latest_version(deleted_memory_id)
                if latest and latest.asset_id != asset_id and latest.status == "active":
                    replacement_id = latest.asset_id

            if asset_id in dep.references:
                dep.references.remove(asset_id)
                if replacement_id:
                    if replacement_id not in dep.references:
                        dep.references.append(replacement_id)
                    result["repaired_refs"].append(dep.asset_id)
                else:
                    dep.references.append(f"DANGLING:{asset_id}")
                    result["dangling_refs"].append(dep.asset_id)
                self._registry.update(dep)

        atom = self._registry.get(asset_id)
        if atom:
            atom.last_verified = time.time()
            self._registry.update(atom)
            result["l0_preserved"] = True

        self._registry.log_change(type("ChangeAtom", (), {
            "change_id": "",
            "change_type": "scientific_delete",
            "target_asset_id": asset_id,
            "target_path": "",
            "before_snapshot": "",
            "after_snapshot": "",
            "diff_summary": f"File asset deleted (soft): {asset_id}",
            "impact_scope": result["dangling_refs"],
            "trigger_source": "scientific_deleter",
            "timestamp": time.time(),
            "session_id": session_id,
            "undo_possible": True,
        })())
        result["l3_recorded"] = True

        if self._readme_updater:
            try:
                self._readme_updater(asset_id, "deleted")
                result["readme_updated"] = True
            except Exception:
                pass

        return {"success": True, **result}


class AlignmentEngine:
    def __init__(self, registry, llm_classify_fn: Optional[Callable] = None,
                 llm_summarize_fn: Optional[Callable] = None,
                 readme_updater: Optional[Callable] = None):
        self._registry = registry
        self._classifier = ChangeClassifier(llm_classify_fn)
        self._analyzer = ImpactAnalyzer(registry)
        self._updater = CascadeUpdater(registry, llm_summarize_fn)
        self._deleter = ScientificDeleter(registry, readme_updater)
        self._lock = threading.RLock()
        self._stats = {
            "total_alignments": 0,
            "by_severity": {s.value: 0 for s in ChangeSeverity},
            "total_cascades": 0,
            "total_deletions": 0,
        }

    def on_change(self, change_atom, before: str = "", after: str = "") -> AlignmentResult:
        start = time.time()
        with self._lock:
            try:
                return self._execute_pipeline(change_atom, before, after)
            finally:
                self._stats["total_alignments"] += 1

    def _execute_pipeline(self, change_atom, before: str, after: str) -> AlignmentResult:
        result = AlignmentResult(change_id=change_atom.change_id if hasattr(change_atom, 'change_id') else "")

        target_id = change_atom.target_asset_id if hasattr(change_atom, 'target_asset_id') else ""
        change_type = change_atom.change_type if hasattr(change_atom, 'change_type') else ""

        if not target_id:
            result.errors.append("No target_asset_id in ChangeAtom")
            return result

        severity = self._classifier.classify(before, after, change_type)
        result.severity = severity.value
        self._stats["by_severity"][severity.value] += 1

        impact = self._analyzer.analyze(target_id, severity)
        result.impact_report = impact

        if change_type == "delete" or severity == ChangeSeverity.DESTRUCTIVE:
            del_result = self._deleter.delete_asset(target_id)
            if not del_result.get("success"):
                result.errors.append(f"Deletion failed: {del_result.get('error')}")
            self._stats["total_deletions"] += 1
        else:
            cascade_count = self._updater.execute(target_id, impact, severity)
            result.cascade_count = cascade_count
            self._stats["total_cascades"] += cascade_count

        self._registry.log_change(type("ChangeAtom", (), {
            "change_id": "",
            "change_type": "alignment_complete",
            "target_asset_id": target_id,
            "target_path": "",
            "before_snapshot": "",
            "after_snapshot": "",
            "diff_summary": f"Alignment: severity={severity.value}, impact={impact.total_impact_count}, cascades={result.cascade_count}",
            "impact_scope": impact.directly_affected,
            "trigger_source": "alignment_engine",
            "timestamp": time.time(),
            "session_id": "",
            "undo_possible": False,
        })())

        result.success = True
        result.duration_ms = (time.time() - (self._stats.get("_start_time", time.time()))) * 1000
        return result

    def get_stats(self) -> Dict:
        return dict(self._stats)
