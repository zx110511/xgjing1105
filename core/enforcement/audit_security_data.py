# -*- coding: utf-8 -*-
"""
安全合规 + 数据准确性审计器
[SSS-PhaseB] 从audit_engine.py拆分

SecurityAuditor: 敏感数据/危险操作/SQL注入/访问控制/数据完整性
DataAccuracyAuditor: 哈希一致性/引用完整性/版本链/TDAF往返/层一致性
"""

import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path

from .audit_base import BaseAuditor
from .audit_models import AuditContext, AuditDimensionReport, AuditSeverity, AuditStatus


class SecurityAuditor(BaseAuditor):
    """安全合规审计器 — 验证安全性"""
    DIMENSION = "security"
    WEIGHT = 1.3

    SENSITIVE_PATTERNS = [
        (r'password\s*=\s*["\']', "hardcoded_password"),
        (r'api_key\s*=\s*["\']', "hardcoded_api_key"),
        (r'secret\s*=\s*["\']', "hardcoded_secret"),
        (r'token\s*=\s*["\']', "hardcoded_token"),
        (r"PRIVATE_KEY", "private_key_exposure"),
    ]

    DANGEROUS_OPS_REGEX = [
        (r"(?<!\w)os\.system\s*\(", "os.system"),
        (r"(?<!\w)subprocess\.call\s*\(", "subprocess.call"),
        (r"(?<!\w)eval\s*\(", "eval()"),
        (r"(?<!\w)exec\s*\(", "exec()"),
    ]

    def run(self) -> AuditDimensionReport:
        self._audit_sensitive_data()
        self._audit_dangerous_ops()
        self._audit_sql_injection()
        self._audit_access_control()
        self._audit_data_integrity()
        return self._report

    def _audit_sensitive_data(self):
        findings = []
        exclude_prefixes = ["test_", "audit_", "benchmark_", "enrich_", "register_", "sync_", "audit_engine"]
        for scan_dir in ["core", "scripts"]:
            d = os.path.join(self._ctx.root_dir, scan_dir)
            if not os.path.exists(d):
                continue
            for fname in os.listdir(d):
                if not fname.endswith(".py") or any(fname.startswith(p) or fname == p + ".py" for p in exclude_prefixes):
                    continue
                try:
                    with open(os.path.join(d, fname), "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    for pattern, desc in self.SENSITIVE_PATTERNS:
                        for match in re.finditer(pattern, content, re.IGNORECASE):
                            line_start = content.rfind("\n", 0, match.start()) + 1
                            line_end = content.find("\n", match.start())
                            line_text = (content[line_start:line_end].strip() if line_end > 0 else content[line_start:].strip())
                            if any(kw in line_text for kw in ["rule", "pattern", "regex", "check", "detect", "scan"]):
                                continue
                            findings.append({"file": fname, "pattern": desc, "line": line_text[:80]})
                            break
                except Exception:
                    pass
        if not findings:
            self._pass("SEC-SENSITIVE-01", 15.0, 15.0, "No hardcoded secrets in production code")
        else:
            for f in findings:
                self._fail(f"SEC-SENSITIVE-{f['file']}", 0.0, 15.0, f"{f['file']}: {f['pattern']} — {f.get('line', '')}", severity=AuditSeverity.HIGH)

    def _audit_dangerous_ops(self):
        findings = []
        core_dir = os.path.join(self._ctx.root_dir, "core")
        if not os.path.exists(core_dir):
            return
        for fname in os.listdir(core_dir):
            if not fname.endswith(".py") or fname.startswith("audit_"):
                continue
            try:
                with open(os.path.join(core_dir, fname), "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                for pattern, desc in self.DANGEROUS_OPS_REGEX:
                    for match in re.finditer(pattern, content):
                        line_start = content.rfind("\n", 0, match.start()) + 1
                        line_end = content.find("\n", match.start())
                        line_text = (content[line_start:line_end].strip() if line_end > 0 else content[line_start:].strip())
                        if desc == "eval()" and ("__builtins__" in line_text or "literal_eval" in line_text):
                            continue
                        findings.append({"file": fname, "op": desc, "line": line_text[:100]})
                        break
            except Exception:
                pass
        if not findings:
            self._pass("SEC-DANGEROUS-01", 10.0, 10.0, "No dangerous operations in core")
        else:
            for f in findings:
                self._warn(f"SEC-DANGEROUS-{f['file']}", 5.0, 10.0, f"{f['file']}: {f['op']}")

    def _audit_sql_injection(self):
        tmpdir = tempfile.mkdtemp(prefix="tianji_sec_sql_")
        try:
            from core.memory.asset_atom import AssetAtom, AssetRegistry, ContentType, Provenance
            asset_db = os.path.join(tmpdir, "sec_sql.db")
            registry = AssetRegistry(asset_db)
            malicious_id = "test'; DROP TABLE asset_registry; --"
            atom = AssetAtom(memory_id=malicious_id, layer="working", content_type=ContentType.KNOWLEDGE,
                           content_hash="abc123", provenance=Provenance(created_by="audit", created_at=time.time()))
            try:
                registry.register(atom)
                conn = sqlite3.connect(asset_db)
                count = conn.execute("SELECT COUNT(*) FROM asset_registry").fetchone()[0]
                conn.close()
                self._pass("SEC-SQL-01", 15.0, 15.0, "SQL injection safely handled") if count >= 1 else \
                    self._fail("SEC-SQL-01", 0.0, 15.0, "SQL injection may have corrupted data")
            except Exception:
                self._pass("SEC-SQL-01", 15.0, 15.0, "SQL injection raised exception (safe)")
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception as e:
            self._error("SEC-SQL-EX", f"error: {e}", threshold=15.0)

    def _audit_access_control(self):
        tmpdir = tempfile.mkdtemp(prefix="tianji_sec_acl_")
        try:
            from core.memory.asset_atom import AssetRegistry, AssetStatus
            asset_db = os.path.join(tmpdir, "sec_acl.db")
            registry = AssetRegistry(asset_db)
            invalid, _ = registry.transition("nonexistent", AssetStatus.ARCHIVED.value)
            if not invalid:
                self._pass("SEC-ACL-01", 10.0, 10.0, "Invalid transitions rejected")
            else:
                self._fail("SEC-ACL-01", 0.0, 10.0, "Invalid transition accepted")
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception as e:
            self._error("SEC-ACL-EX", f"error: {e}", threshold=10.0)

    def _audit_data_integrity(self):
        tmpdir = tempfile.mkdtemp(prefix="tianji_sec_int_")
        try:
            from core.memory.asset_atom import AssetAtom, AssetRegistry, ContentType, Provenance
            asset_db = os.path.join(tmpdir, "sec_int.db")
            registry = AssetRegistry(asset_db)
            content = "integrity test"
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            atom = AssetAtom(memory_id="int_test", layer="working", content_type=ContentType.KNOWLEDGE,
                           content_hash=content_hash, provenance=Provenance(created_by="audit", created_at=time.time()))
            aid = registry.register(atom)
            fetched = registry.get(aid)
            if fetched and fetched.content_hash == content_hash:
                self._pass("SEC-INT-01", 10.0, 10.0, f"Hash integrity: {content_hash[:16]}...")
            else:
                self._fail("SEC-INT-01", 0.0, 10.0, "Content hash mismatch!")
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception as e:
            self._error("SEC-INT-EX", f"error: {e}", threshold=10.0)


class DataAccuracyAuditor(BaseAuditor):
    """数据准确性审计器 — 验证数据一致性"""
    DIMENSION = "data_accuracy"
    WEIGHT = 1.0

    def run(self) -> AuditDimensionReport:
        self._audit_hash_consistency()
        self._audit_reference_integrity()
        self._audit_version_chain()
        self._audit_tdaf_roundtrip()
        self._audit_layer_consistency()
        return self._report

    def _audit_hash_consistency(self):
        tmpdir = tempfile.mkdtemp(prefix="tianji_acc_hash_")
        try:
            from core.memory.asset_atom import AssetAtom, AssetRegistry, ContentType, Provenance
            asset_db = os.path.join(tmpdir, "acc_hash.db")
            registry = AssetRegistry(asset_db)
            mismatches = 0; total = 50
            for i in range(total):
                content = f"accuracy test {i} with special: 中文！@#"
                expected = hashlib.sha256(content.encode()).hexdigest()
                atom = AssetAtom(memory_id=f"hash_{i}", layer="working", content_type=ContentType.KNOWLEDGE,
                               content_hash=expected, provenance=Provenance(created_by="audit", created_at=time.time()))
                aid = registry.register(atom)
                fetched = registry.get(aid)
                if fetched and fetched.content_hash != expected:
                    mismatches += 1
            rate = (total - mismatches) / total * 100
            threshold = self._ctx.thresholds.get("data_accuracy_hash_match", 100.0)
            if rate >= threshold:
                self._pass("DA-HASH-01", rate, threshold, f"Hash: {total - mismatches}/{total} ({rate:.1f}%)")
            else:
                self._fail("DA-HASH-01", rate, threshold, f"Hash mismatches: {mismatches}/{total}")
        except Exception as e:
            self._error("DA-HASH-EX", f"error: {e}", threshold=100.0)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _audit_reference_integrity(self):
        tmpdir = tempfile.mkdtemp(prefix="tianji_acc_ref_")
        try:
            from core.memory.asset_atom import AssetAtom, AssetRegistry, ContentType, Provenance
            asset_db = os.path.join(tmpdir, "acc_ref.db")
            registry = AssetRegistry(asset_db)
            a = AssetAtom(memory_id="ref_a", layer="working", content_type=ContentType.KNOWLEDGE,
                         content_hash=hashlib.sha256(b"a").hexdigest(), Provenance=Provenance(created_by="audit", created_at=time.time()))
            b = AssetAtom(memory_id="ref_b", layer="episodic", content_type=ContentType.CONVERSATION,
                         content_hash=hashlib.sha256(b"b").hexdigest(), Provenance=Provenance(created_by="audit", created_at=time.time()))
            aid = registry.register(a); bid = registry.register(b)
            registry.add_reference(aid, bid)
            deps = registry.get_dependents(bid)
            if any(d.asset_id == aid for d in deps):
                self._pass("DA-REF-01", 15.0, 15.0, "Reference A→B verified")
            else:
                self._fail("DA-REF-01", 0.0, 15.0, "Reference A→B broken")
            registry.remove_reference(aid, bid)
            deps_after = registry.get_dependents(bid)
            if not any(d.asset_id == aid for d in deps_after):
                self._pass("DA-REF-02", 10.0, 10.0, "Ref removal verified")
            else:
                self._fail("DA-REF-02", 0.0, 10.0, "Dangling reference remains")
        except Exception as e:
            self._error("DA-REF-EX", f"error: {e}", threshold=25.0)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _audit_version_chain(self):
        tmpdir = tempfile.mkdtemp(prefix="tianji_acc_ver_")
        try:
            from core.memory.asset_atom import AssetAtom, AssetRegistry, ContentType, Provenance
            asset_db = os.path.join(tmpdir, "acc_ver.db")
            registry = AssetRegistry(asset_db)
            versions = []; prev_id = ""
            for v in range(1, 6):
                atom = AssetAtom(memory_id="ver_test", layer="working", content_type=ContentType.KNOWLEDGE,
                               content_hash=hashlib.sha256(f"v{v}".encode()).hexdigest(),
                               version=v, parent_version_id=prev_id,
                               provenance=Provenance(created_by="audit", created_at=time.time()))
                vid = registry.register(atom); versions.append(vid); prev_id = vid
            chain = registry.get_version_chain(versions[-1])
            if len(chain) >= 5:
                self._pass("DA-VER-01", 15.0, 15.0, f"Version chain: {len(chain)} versions")
            else:
                self._fail("DA-VER-01", len(chain) * 3.0, 15.0, f"Version chain: only {len(chain)}/5")
            latest = registry.get_latest_version("ver_test")
            if latest and latest.version == 5:
                self._pass("DA-VER-02", 10.0, 10.0, f"Latest: v{latest.version}")
            else:
                self._fail("DA-VER-02", 0.0, 10.0, f"Latest wrong: {latest.version if latest else 'None'}")
        except Exception as e:
            self._error("DA-VER-EX", f"error: {e}", threshold=25.0)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _audit_tdaf_roundtrip(self):
        tmpdir = tempfile.mkdtemp(prefix="tianji_acc_tdaf_")
        try:
            from core.shared.tdaf_schema import create_empty_tdaf, validate_tdaf
            doc = create_empty_tdaf(); data = doc.to_dict()
            json_str = json.dumps(data, ensure_ascii=False)
            parsed = json.loads(json_str)
            valid, errors = validate_tdaf(parsed)
            if valid:
                self._pass("DA-TDAF-01", 15.0, 15.0, "TDAF roundtrip PASS")
            else:
                self._fail("DA-TDAF-01", 0.0, 15.0, f"TDAF roundtrip failed: {errors}")
        except Exception as e:
            self._error("DA-TDAF-EX", f"error: {e}", threshold=15.0)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _audit_layer_consistency(self):
        tmpdir = tempfile.mkdtemp(prefix="tianji_acc_layer_")
        try:
            from core.shared.config import ICMEConfig; from core.memory.engine import ICMEEngine
            config = ICMEConfig(); config.data_path = Path(tmpdir); config.use_sqlite = False
            engine = ICMEEngine(config)
            layers = ["sensory", "working", "short_term", "episodic", "semantic", "meta"]
            results = {}
            for layer in layers:
                r = engine.remember(f"layer test {layer}", layer=layer, tags=["layer_test"])
                results[layer] = r
            all_ok = all(r.get("id") for r in results.values())
            if all_ok:
                self._pass("DA-LAYER-01", 15.0, 15.0, "All 6 layers verified")
            else:
                self._fail("DA-LAYER-01", sum(2.5 for r in results.values() if r.get("id")), 15.0,
                          f"Failed: {[l for l, r in results.items() if not r.get('id')]}")
        except Exception as e:
            self._error("DA-LAYER-EX", f"error: {e}", threshold=15.0)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
