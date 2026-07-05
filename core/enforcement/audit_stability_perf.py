# -*- coding: utf-8 -*-
"""
稳定性 + 性能审计器
[SSS-PhaseB] 从audit_engine.py拆分

StabilityAuditor: 重复操作/并发访问/错误恢复/资源清理
PerformanceAuditor: remember/recall/export/吞吐/批量性能
"""

import hashlib
import os
import shutil
import sqlite3
import statistics
import tempfile
import threading
import time
from pathlib import Path

from .audit_base import BaseAuditor
from .audit_models import AuditContext, AuditDimensionReport, AuditSeverity, AuditStatus


class StabilityAuditor(BaseAuditor):
    """稳定性审计器 — 验证系统稳定性"""
    DIMENSION = "stability"
    WEIGHT = 1.2
    ITERATIONS = 5

    def run(self) -> AuditDimensionReport:
        self._audit_repeated_operations()
        self._audit_concurrent_access()
        self._audit_error_recovery()
        self._audit_resource_cleanup()
        return self._report

    def _audit_repeated_operations(self):
        tmpdir = tempfile.mkdtemp(prefix="tianji_stab_rep_")
        asset_db = os.path.join(tmpdir, "stab.db")
        try:
            from core.memory.asset_atom import AssetAtom, AssetRegistry, ContentType, Provenance
            registry = AssetRegistry(asset_db)
            success_count = 0
            latencies = []
            for i in range(self.ITERATIONS):
                t0 = time.time()
                try:
                    atom = AssetAtom(memory_id=f"stab_{i}", layer="working", content_type=ContentType.KNOWLEDGE,
                                   content_hash=hashlib.sha256(f"stab_{i}".encode()).hexdigest(),
                                   provenance=Provenance(created_by="audit", created_at=time.time()))
                    aid = registry.register(atom)
                    fetched = registry.get(aid)
                    dt = (time.time() - t0) * 1000
                    latencies.append(dt)
                    if fetched and fetched.memory_id == f"stab_{i}":
                        success_count += 1
                except Exception:
                    latencies.append((time.time() - t0) * 1000)

            pass_rate = success_count / self.ITERATIONS * 100
            threshold = self._ctx.thresholds.get("stability_pass_rate", 95.0)
            avg_lat = statistics.mean(latencies) if latencies else 0
            if pass_rate >= threshold:
                self._pass("S-REPEAT-01", pass_rate, threshold, f"Repeated: {success_count}/{self.ITERATIONS}, avg={avg_lat:.1f}ms")
            else:
                self._fail("S-REPEAT-01", pass_rate, threshold, f"Repeated: only {success_count}/{self.ITERATIONS}")
        except Exception as e:
            self._error("S-REPEAT-01", f"error: {e}", threshold=95.0)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _audit_concurrent_access(self):
        tmpdir = tempfile.mkdtemp(prefix="tianji_stab_conc_")
        asset_db = os.path.join(tmpdir, "stab_conc.db")
        try:
            from core.memory.asset_atom import AssetAtom, AssetRegistry, ContentType, Provenance
            registry = AssetRegistry(asset_db)
            errors_list, success_list = [], []
            lock = threading.Lock()

            def worker(idx):
                try:
                    atom = AssetAtom(memory_id=f"conc_{idx}", layer="working", content_type=ContentType.KNOWLEDGE,
                                   content_hash=hashlib.sha256(f"conc_{idx}".encode()).hexdigest(),
                                   Provenance=Provenance(created_by="audit", created_at=time.time()))
                    aid = registry.register(atom)
                    fetched = registry.get(aid)
                    with lock:
                        (success_list if fetched else errors_list).append(idx)
                except Exception as e:
                    with lock:
                        errors_list.append(str(e))

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10.0)

            pass_rate = len(success_list) / 10 * 100
            threshold = self._ctx.thresholds.get("stability_pass_rate", 95.0)
            if pass_rate >= threshold:
                self._pass("S-CONCURRENT-01", pass_rate, threshold, f"Concurrent: {len(success_list)}/10 success")
            else:
                self._warn("S-CONCURRENT-01", pass_rate, threshold, f"Concurrent: {len(success_list)}/10, errors={errors_list[:3]}")
        except Exception as e:
            self._error("S-CONCURRENT-01", f"error: {e}", threshold=95.0)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _audit_error_recovery(self):
        try:
            from core.memory.asset_atom import AssetRegistry, AssetStatus
            tmpdir = tempfile.mkdtemp(prefix="tianji_stab_err_")
            asset_db = os.path.join(tmpdir, "stab_err.db")
            registry = AssetRegistry(asset_db)
            invalid, _ = registry.transition("nonexistent_id", AssetStatus.DELETED.value)
            if not invalid:
                self._pass("S-ERR-01", 10.0, 10.0, "Invalid transition rejected")
            else:
                self._fail("S-ERR-01", 0.0, 10.0, "Invalid transition should be rejected")

            fetched = registry.get("nonexistent_id")
            if fetched is None:
                self._pass("S-ERR-02", 10.0, 10.0, "Nonexistent returns None")
            else:
                self._fail("S-ERR-02", 0.0, 10.0, "Nonexistent should return None")
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception as e:
            self._error("S-ERR-EX", f"error: {e}", threshold=20.0)

    def _audit_resource_cleanup(self):
        tmpdir = tempfile.mkdtemp(prefix="tianji_stab_clean_")
        try:
            from core.memory.asset_atom import AssetAtom, AssetRegistry, ContentType, Provenance
            asset_db = os.path.join(tmpdir, "stab_clean.db")
            registry = AssetRegistry(asset_db)
            for i in range(50):
                atom = AssetAtom(memory_id=f"clean_{i}", layer="working", content_type=ContentType.KNOWLEDGE,
                               content_hash=hashlib.sha256(f"clean_{i}".encode()).hexdigest(),
                               provenance=Provenance(created_by="audit", created_at=time.time()))
                registry.register(atom)
            conn = sqlite3.connect(asset_db)
            count = conn.execute("SELECT COUNT(*) FROM asset_registry").fetchone()[0]
            conn.close()
            if count >= 50:
                self._pass("S-CLEAN-01", 10.0, 10.0, f"50 assets persisted: count={count}")
            else:
                self._fail("S-CLEAN-01", 0.0, 10.0, f"Only {count}/50 persisted")
        except Exception as e:
            self._error("S-CLEAN-EX", f"error: {e}", threshold=10.0)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class PerformanceAuditor(BaseAuditor):
    """性能审计器 — 验证系统性能指标"""
    DIMENSION = "performance"
    WEIGHT = 1.0
    WARMUP_OPS = 5
    BENCHMARK_OPS = 50

    def run(self) -> AuditDimensionReport:
        self._audit_remember_performance()
        self._audit_recall_performance()
        self._audit_export_performance()
        self._audit_throughput()
        self._audit_batch_performance()
        return self._report

    def _audit_remember_performance(self):
        tmpdir = tempfile.mkdtemp(prefix="tianji_perf_rem_")
        try:
            from core.shared.config import ICMEConfig
            from core.memory.engine import ICMEEngine
            config = ICMEConfig(); config.data_path = Path(tmpdir); config.use_sqlite = False
            engine = ICMEEngine(config)
            for _ in range(self.WARMUP_OPS):
                engine.remember("warmup", layer="working")
            latencies = []
            for i in range(self.BENCHMARK_OPS):
                t0 = time.time()
                engine.remember(f"perf_{i}", layer="working", tags=["perf"])
                latencies.append((time.time() - t0) * 1000)
            avg = statistics.mean(latencies)
            p95 = sorted(latencies)[int(len(latencies) * 0.95)]
            p99 = sorted(latencies)[int(len(latencies) * 0.99)]
            threshold = self._ctx.thresholds.get("performance_remember_ms", 500.0)
            if p95 <= threshold:
                self._pass("P-REMEMBER-01", threshold - p95 + 50, threshold, f"remember() p95={p95:.1f}ms avg={avg:.1f}ms p99={p99:.1f}ms")
            else:
                self._warn("P-REMEMBER-01", max(0, threshold - p95 + 50), threshold, f"remember() p95={p95:.1f}ms EXCEEDS {threshold}ms")
        except Exception as e:
            self._error("P-REMEMBER-EX", f"error: {e}", threshold=500.0)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _audit_recall_performance(self):
        tmpdir = tempfile.mkdtemp(prefix="tianji_perf_rec_")
        try:
            from core.shared.config import ICMEConfig; from core.memory.engine import ICMEEngine
            config = ICMEConfig(); config.data_path = Path(tmpdir); config.use_sqlite = False
            engine = ICMEEngine(config)
            for i in range(20):
                engine.remember(f"recall_{i}", layer="working", tags=[f"tag_{i % 5}"])
            latencies = []
            for _ in range(self.BENCHMARK_OPS):
                t0 = time.time()
                engine.recall("recall", limit=5)
                latencies.append((time.time() - t0) * 1000)
            p95 = sorted(latencies)[int(len(latencies) * 0.95)]
            threshold = self._ctx.thresholds.get("performance_recall_ms", 200.0)
            if p95 <= threshold:
                self._pass("P-RECALL-01", threshold - p95 + 20, threshold, f"recall() p95={p95:.1f}ms")
            else:
                self._warn("P-RECALL-01", max(0, threshold - p95 + 20), threshold, f"recall() p95={p95:.1f}ms EXCEEDS {threshold}ms")
        except Exception as e:
            self._error("P-RECALL-EX", f"error: {e}", threshold=200.0)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _audit_export_performance(self):
        tmpdir = tempfile.mkdtemp(prefix="tianji_perf_exp_")
        try:
            from core.memory.asset_atom import AssetAtom, AssetRegistry, ContentType, Provenance
            from core.shared.tdaf_exporter import TDAFExporter
            asset_db = os.path.join(tmpdir, "perf_assets.db")
            registry = AssetRegistry(asset_db)
            for i in range(100):
                atom = AssetAtom(memory_id=f"exp_{i}", layer=["sensory", "working", "episodic"][i % 3],
                               content_type=ContentType.KNOWLEDGE,
                               content_hash=hashlib.sha256(f"exp_{i}".encode()).hexdigest(),
                               provenance=Provenance(created_by="audit", created_at=time.time()))
                registry.register(atom)
            exporter = TDAFExporter(asset_db, registry=registry)
            out_path = os.path.join(tmpdir, "perf_export.json")
            t0 = time.time()
            result = exporter.export_full(out_path)
            dt = (time.time() - t0) * 1000
            threshold = self._ctx.thresholds.get("performance_export_ms", 5000.0)
            if result["success"] and dt <= threshold:
                self._pass("P-EXPORT-01", threshold - dt + 100, threshold, f"export_full(100): {dt:.1f}ms")
            elif result["success"]:
                self._warn("P-EXPORT-01", max(0, threshold - dt + 100), threshold, f"export_full: {dt:.1f}ms EXCEEDS {threshold}ms")
            else:
                self._fail("P-EXPORT-01", 0.0, threshold, "export_full FAILED")
        except Exception as e:
            self._error("P-EXPORT-EX", f"error: {e}", threshold=5000.0)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _audit_throughput(self):
        tmpdir = tempfile.mkdtemp(prefix="tianji_perf_thr_")
        try:
            from core.memory.asset_atom import AssetAtom, AssetRegistry, ContentType, Provenance
            asset_db = os.path.join(tmpdir, "perf_thr.db")
            registry = AssetRegistry(asset_db)
            t0 = time.time(); count = 0
            while time.time() - t0 < 2.0:
                atom = AssetAtom(memory_id=f"thr_{count}", layer="working", content_type=ContentType.KNOWLEDGE,
                               content_hash=hashlib.sha256(f"thr_{count}".encode()).hexdigest(),
                               provenance=Provenance(created_by="audit", created_at=time.time()))
                registry.register(atom); count += 1
            elapsed = time.time() - t0
            ops_per_sec = count / elapsed
            threshold = self._ctx.thresholds.get("performance_throughput_ops", 50.0)
            if ops_per_sec >= threshold:
                self._pass("P-THROUGHPUT-01", ops_per_sec, threshold, f"Throughput: {ops_per_sec:.1f} ops/sec")
            else:
                self._warn("P-THROUGHPUT-01", ops_per_sec, threshold, f"Throughput: {ops_per_sec:.1f} ops/sec BELOW {threshold}")
        except Exception as e:
            self._error("P-THROUGHPUT-EX", f"error: {e}", threshold=50.0)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _audit_batch_performance(self):
        tmpdir = tempfile.mkdtemp(prefix="tianji_perf_batch_")
        try:
            from scripts.register_historical_assets import HistoricalAssetRegistrar
            test_db = os.path.join(tmpdir, "perf_batch.db")
            tc = sqlite3.connect(test_db)
            tc.execute("""CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY, content TEXT, layer TEXT, tags TEXT DEFAULT '[]',
                priority TEXT DEFAULT 'medium', value_score REAL DEFAULT 0.5,
                created_at REAL, metadata TEXT DEFAULT '{}', archived INTEGER DEFAULT 0,
                last_accessed REAL DEFAULT 0, size_bytes INTEGER DEFAULT 0,
                content_segmented TEXT DEFAULT '', related_ids TEXT DEFAULT '[]',
                changelog TEXT DEFAULT '[]'
            )""")
            for i in range(200):
                tc.execute("INSERT INTO memories (id, content, layer, created_at) VALUES (?,?,?,?)",
                          (f"batch_{i}", f"batch content {i}",
                           ["sensory", "working", "short_term", "episodic", "semantic"][i % 5], time.time()))
            tc.commit(); tc.close()
            hist_db = os.path.join(tmpdir, "perf_batch_assets.db")
            t0 = time.time()
            registrar = HistoricalAssetRegistrar(db_path=test_db, asset_db_path=hist_db)
            reg_result = registrar.register_all()
            dt = (time.time() - t0) * 1000
            if reg_result["registered"] >= 200:
                rate = reg_result["registered"] / (dt / 1000)
                self._pass("P-BATCH-01", 10.0, 10.0, f"Batch: {reg_result['registered']} in {dt:.1f}ms ({rate:.0f} ops/sec)")
            else:
                self._fail("P-BATCH-01", 0.0, 10.0, f"Batch: only {reg_result['registered']}/200")
        except Exception as e:
            self._error("P-BATCH-EX", f"error: {e}", threshold=10.0)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
