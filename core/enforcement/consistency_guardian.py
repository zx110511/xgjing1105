r"""
ConsistencyGuardian - 天机一致性守护 v1.0
==========================================
D15: 定期扫描资产完整性，修复断裂引用
verify_references / verify_hashes / verify_layer_consistency
verify_version_chain / repair_dangling_refs / run_full_audit
"""

import time
import json
import hashlib
import threading
from dataclasses import dataclass, field, asdict
from typing import Any, Optional, List, Dict, Tuple


@dataclass
class VerifyResult:
    check_name: str = ""
    passed: bool = True
    total_checked: int = 0
    issues_found: int = 0
    issues: List[Dict] = field(default_factory=list)
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AuditReport:
    timestamp: float = field(default_factory=time.time)
    total_checks: int = 0
    total_passed: int = 0
    total_issues: int = 0
    auto_repaired: int = 0
    results: List[VerifyResult] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["results"] = [r.to_dict() if hasattr(r, 'to_dict') else r for r in self.results]
        return d


class ConsistencyGuardian:
    def __init__(self, registry, engine=None):
        self._registry = registry
        self._engine = engine
        self._lock = threading.RLock()
        self._last_audit: Optional[AuditReport] = None

    def verify_references(self) -> VerifyResult:
        start = time.time()
        result = VerifyResult(check_name="verify_references")

        conn = self._registry._get_conn()
        try:
            rows = conn.execute(
                "SELECT asset_id, references_ids, referenced_by_ids FROM asset_registry WHERE status != 'archived'"
            ).fetchall()
        finally:
            conn.close()

        result.total_checked = len(rows)

        for row in rows:
            asset_id = row["asset_id"]
            refs = json.loads(row["references_ids"])
            ref_by = json.loads(row["referenced_by_ids"])

            for ref_id in refs:
                if ref_id.startswith("DANGLING:"):
                    result.issues_found += 1
                    result.issues.append({
                        "type": "dangling_reference",
                        "asset_id": asset_id,
                        "reference": ref_id,
                        "detail": f"Asset {asset_id} has dangling reference to {ref_id}",
                    })
                    continue

                target = self._registry.get(ref_id)
                if not target:
                    result.issues_found += 1
                    result.issues.append({
                        "type": "broken_reference",
                        "asset_id": asset_id,
                        "reference": ref_id,
                        "detail": f"Asset {asset_id} references non-existent {ref_id}",
                    })

            for ref_id in ref_by:
                if ref_id.startswith("DANGLING:"):
                    continue
                source = self._registry.get(ref_id)
                if not source:
                    result.issues_found += 1
                    result.issues.append({
                        "type": "broken_referenced_by",
                        "asset_id": asset_id,
                        "referenced_by": ref_id,
                        "detail": f"Asset {asset_id} referenced by non-existent {ref_id}",
                    })

        result.passed = result.issues_found == 0
        result.duration_ms = (time.time() - start) * 1000
        return result

    def verify_hashes(self, content_provider: Optional[callable] = None) -> VerifyResult:
        start = time.time()
        result = VerifyResult(check_name="verify_hashes")

        conn = self._registry._get_conn()
        try:
            rows = conn.execute(
                "SELECT asset_id, memory_id, content_hash FROM asset_registry WHERE status = 'active'"
            ).fetchall()
        finally:
            conn.close()

        result.total_checked = len(rows)

        if content_provider:
            for row in rows:
                asset_id = row["asset_id"]
                stored_hash = row["content_hash"]
                try:
                    actual_content = content_provider(row["memory_id"])
                    if actual_content:
                        actual_hash = hashlib.sha256(actual_content.encode("utf-8")).hexdigest()
                        if actual_hash != stored_hash:
                            result.issues_found += 1
                            result.issues.append({
                                "type": "hash_mismatch",
                                "asset_id": asset_id,
                                "stored_hash": stored_hash[:8],
                                "actual_hash": actual_hash[:8],
                            })
                except Exception:
                    pass

        result.passed = result.issues_found == 0
        result.duration_ms = (time.time() - start) * 1000
        return result

    def verify_layer_consistency(self) -> VerifyResult:
        start = time.time()
        result = VerifyResult(check_name="verify_layer_consistency")

        conn = self._registry._get_conn()
        try:
            rows = conn.execute(
                "SELECT asset_id, memory_id, layer FROM asset_registry WHERE status = 'active'"
            ).fetchall()
        finally:
            conn.close()

        result.total_checked = len(rows)

        layer_counts = {}
        for row in rows:
            layer = row["layer"]
            layer_counts[layer] = layer_counts.get(layer, 0) + 1

        valid_layers = {"sensory", "working", "short_term", "episodic", "semantic", "meta"}
        for row in rows:
            if row["layer"] not in valid_layers:
                result.issues_found += 1
                result.issues.append({
                    "type": "invalid_layer",
                    "asset_id": row["asset_id"],
                    "layer": row["layer"],
                })

        result.passed = result.issues_found == 0
        result.duration_ms = (time.time() - start) * 1000
        return result

    def verify_version_chain(self) -> VerifyResult:
        start = time.time()
        result = VerifyResult(check_name="verify_version_chain")

        conn = self._registry._get_conn()
        try:
            rows = conn.execute(
                "SELECT asset_id, memory_id, version, parent_version_id FROM asset_registry WHERE status != 'archived'"
            ).fetchall()
        finally:
            conn.close()

        result.total_checked = len(rows)

        for row in rows:
            parent_id = row["parent_version_id"]
            if parent_id:
                parent = self._registry.get(parent_id)
                if not parent:
                    result.issues_found += 1
                    result.issues.append({
                        "type": "broken_version_chain",
                        "asset_id": row["asset_id"],
                        "parent_version_id": parent_id,
                        "detail": f"Parent version {parent_id} not found",
                    })

        result.passed = result.issues_found == 0
        result.duration_ms = (time.time() - start) * 1000
        return result

    def repair_dangling_refs(self) -> Tuple[int, List[Dict]]:
        repairs = []
        repair_count = 0

        conn = self._registry._get_conn()
        try:
            rows = conn.execute(
                "SELECT asset_id, references_ids, referenced_by_ids FROM asset_registry WHERE status != 'archived'"
            ).fetchall()
        finally:
            conn.close()

        for row in rows:
            asset_id = row["asset_id"]
            refs = json.loads(row["references_ids"])
            ref_by = json.loads(row["referenced_by_ids"])

            new_refs = []
            changed = False
            for ref_id in refs:
                if ref_id.startswith("DANGLING:"):
                    original_id = ref_id.replace("DANGLING:", "")
                    latest = self._registry.get_latest_version(
                        self._get_memory_id_for_asset(original_id)
                    )
                    if latest and latest.asset_id != original_id:
                        new_refs.append(latest.asset_id)
                        repair_count += 1
                        repairs.append({
                            "type": "ref_repaired",
                            "asset_id": asset_id,
                            "old_ref": ref_id,
                            "new_ref": latest.asset_id,
                        })
                        changed = True
                    else:
                        new_refs.append(ref_id)
                else:
                    new_refs.append(ref_id)

            if changed:
                atom = self._registry.get(asset_id)
                if atom:
                    atom.references = new_refs
                    atom.updated_at = time.time()
                    self._registry.update(atom)

        return repair_count, repairs

    def _get_memory_id_for_asset(self, asset_id: str) -> str:
        atom = self._registry.get(asset_id)
        return atom.memory_id if atom else ""

    def run_full_audit(self) -> AuditReport:
        start = time.time()
        report = AuditReport()

        checks = [
            self.verify_references(),
            self.verify_layer_consistency(),
            self.verify_version_chain(),
        ]

        for check_result in checks:
            report.results.append(check_result)
            report.total_checks += 1
            if check_result.passed:
                report.total_passed += 1
            report.total_issues += check_result.issues_found

        repair_count, repairs = self.repair_dangling_refs()
        report.auto_repaired = repair_count

        report.summary = (
            f"Audit complete: {report.total_passed}/{report.total_checks} checks passed, "
            f"{report.total_issues} issues found, {report.auto_repaired} auto-repaired"
        )

        self._last_audit = report
        return report

    def get_last_audit(self) -> Optional[AuditReport]:
        return self._last_audit
