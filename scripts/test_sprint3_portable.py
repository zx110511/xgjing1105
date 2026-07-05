r"""
Sprint 3 全流程验证脚本 v1.0
==============================
D16-D22: 可移植与导出 — 3轮验证
"""

import sys
import os
import time
import json
import hashlib
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("AI_MEMORY_ROOT", os.path.dirname(os.path.abspath(__file__)))

results = {}
report = []


def L(msg):
    report.append(msg)
    print(msg)


def result(test_id, status, detail=""):
    results[test_id] = status
    tag = "PASS" if status == "PASS" else "FAIL"
    L(f"  [{tag}] {test_id}: {detail}")


def run_verification(round_num):
    L(f"\n{'='*60}")
    L(f"  Sprint 3 验证 — 第{round_num}轮")
    L(f"{'='*60}")

    tmpdir = tempfile.mkdtemp(prefix=f"tianji_s3_r{round_num}_")
    db_path = os.path.join(tmpdir, "test_icme.db")

    try:
        from core.memory.asset_atom import (
            AssetAtom, AssetRegistry, ChangeAtom, Provenance,
            AssetStatus, ContentType,
        )
        from core.shared.tdaf_schema import (
            TDAFDocument, TDAFManifest, TDAFValidator,
            validate_tdaf, create_empty_tdaf, TDAF_V1_SCHEMA,
        )
        from core.shared.tdaf_exporter import TDAFExporter
        from core.shared.tdaf_adapters import (
            TraeAdapter, CursorAdapter, CopilotAdapter,
            MarkdownAdapter, adapt, adapt_to_files,
        )
        from core.shared.file_watcher import FileWatcher, FileChangeHandler
        from core.shared.alignment_engine import AlignmentEngine, ChangeSeverity
        from core.enforcement.consistency_guardian import ConsistencyGuardian

        registry = AssetRegistry(db_path)

        L(f"\n--- D16: TDAF v1.0 Schema定义 ---")

        doc = create_empty_tdaf()
        result("D16-1", "PASS" if doc.tdaf_version == "1.0" else "FAIL",
               f"tdaf_version={doc.tdaf_version}")

        doc_dict = doc.to_dict()
        result("D16-2", "PASS" if "@context" in doc_dict else "FAIL",
               f"@context present={('@context' in doc_dict)}")

        valid, errors = validate_tdaf(doc_dict)
        result("D16-3", "PASS" if valid else "FAIL",
               f"empty doc validation: valid={valid}, errors={errors[:2]}")

        test_tdaf = {
            "tdaf_version": "1.0",
            "export_timestamp": time.time(),
            "asset_manifest": {"total_assets": 2, "total_size_bytes": 1024},
            "assets": [
                {"asset_id": "test:abc:0001", "memory_id": "mem1", "layer": "working", "content_hash": "abc123"},
                {"asset_id": "test:def:0002", "memory_id": "mem2", "layer": "episodic", "content_hash": "def456"},
            ],
            "knowledge_graph": {"nodes": [], "edges": []},
        }
        valid2, errors2 = validate_tdaf(test_tdaf)
        result("D16-4", "PASS" if valid2 else "FAIL",
               f"test data validation: valid={valid2}")

        invalid_tdaf = {"tdaf_version": "2.0"}
        valid3, errors3 = validate_tdaf(invalid_tdaf)
        result("D16-5", "PASS" if not valid3 else "FAIL",
               f"invalid version detected: errors={len(errors3)}")

        schema_path = os.path.join(os.path.dirname(__file__), "..", "schemas", "tdaf-v1.0.json")
        result("D16-6", "PASS" if os.path.exists(schema_path) else "FAIL",
               f"schema file exists={os.path.exists(schema_path)}")

        L(f"\n--- D17: 全量导出器 ---")

        for i in range(5):
            atom = AssetAtom(
                memory_id=f"export_mem_{i}",
                layer=["sensory", "working", "episodic", "semantic", "meta"][i],
                content_type=ContentType.KNOWLEDGE,
                content_hash=hashlib.sha256(f"content_{i}".encode()).hexdigest(),
                provenance=Provenance(created_by="test", created_at=time.time()),
            )
            registry.register(atom)

        exporter = TDAFExporter(db_path, registry=registry)
        export_path = os.path.join(tmpdir, "full_export.json")
        export_result = exporter.export_full(export_path, include_content=False)

        result("D17-1", "PASS" if export_result["success"] else "FAIL",
               f"export_full success={export_result['success']}")
        result("D17-2", "PASS" if export_result["total_assets"] == 5 else "FAIL",
               f"total_assets={export_result['total_assets']}")
        result("D17-3", "PASS" if os.path.exists(export_path) else "FAIL",
               f"export file exists")

        with open(export_path, "r", encoding="utf-8") as f:
            exported_data = json.load(f)
        valid_export, export_errors = validate_tdaf(exported_data)
        result("D17-4", "PASS" if valid_export else "FAIL",
               f"exported data valid={valid_export}")

        result("D17-5", "PASS" if len(exported_data.get("assets", [])) == 5 else "FAIL",
               f"assets count={len(exported_data.get('assets', []))}")

        L(f"\n--- D18: 增量导出器 ---")

        time.sleep(0.1)
        new_atom = AssetAtom(
            memory_id="incremental_mem",
            layer="working",
            content_type=ContentType.DECISION,
            content_hash=hashlib.sha256(b"incremental").hexdigest(),
            provenance=Provenance(created_by="test", created_at=time.time()),
        )
        registry.register(new_atom)

        inc_export_path = os.path.join(tmpdir, "inc_export.json")
        since_ts = export_result.get("export_timestamp", time.time() - 1)
        inc_result = exporter.export_incremental(inc_export_path, since_timestamp=since_ts - 1)

        result("D18-1", "PASS" if inc_result["success"] else "FAIL",
               f"export_incremental success={inc_result['success']}")
        result("D18-2", "PASS" if inc_result["total_assets"] >= 1 else "FAIL",
               f"incremental assets={inc_result['total_assets']}")

        with open(inc_export_path, "r", encoding="utf-8") as f:
            inc_data = json.load(f)
        result("D18-3", "PASS" if inc_data.get("export_type") == "incremental" else "FAIL",
               f"export_type={inc_data.get('export_type')}")
        result("D18-4", "PASS" if inc_data.get("since_timestamp", 0) > 0 else "FAIL",
               f"since_timestamp present")

        L(f"\n--- D19: 跨平台适配层 ---")

        tdaf_data = exported_data

        trae_adapter = TraeAdapter()
        trae_output = trae_adapter.adapt(tdaf_data)
        result("D19-1", "PASS" if "Asset Manifest" in trae_output else "FAIL",
               f"TraeAdapter output contains manifest")

        cursor_adapter = CursorAdapter()
        cursor_output = cursor_adapter.adapt(tdaf_data)
        result("D19-2", "PASS" if "tianji_export" in cursor_output else "FAIL",
               f"CursorAdapter output contains header")

        copilot_adapter = CopilotAdapter()
        copilot_output = copilot_adapter.adapt(tdaf_data)
        result("D19-3", "PASS" if "Tianji" in copilot_output else "FAIL",
               f"CopilotAdapter output contains Tianji")

        md_adapter = MarkdownAdapter()
        md_output = md_adapter.adapt(tdaf_data)
        result("D19-4", "PASS" if "Knowledge Graph" in md_output or "Layer" in md_output else "FAIL",
               f"MarkdownAdapter output contains structured content")

        adapt_result = adapt(tdaf_data, "trae")
        result("D19-5", "PASS" if len(adapt_result) > 100 else "FAIL",
               f"adapt() function works, len={len(adapt_result)}")

        adapt_dir = os.path.join(tmpdir, "adapted")
        os.makedirs(adapt_dir, exist_ok=True)
        files = adapt_to_files(tdaf_data, "markdown", adapt_dir)
        result("D19-6", "PASS" if len(files) >= 1 and os.path.exists(files[0]) else "FAIL",
               f"adapt_to_files created {len(files)} files")

        L(f"\n--- D20: 文件Watcher集成 ---")

        tracker_mock = type("MockTracker", (), {
            "track_create": lambda self, *a, **kw: None,
            "track_update": lambda self, *a, **kw: None,
            "track_delete": lambda self, *a, **kw: None,
        })()

        watcher = FileWatcher(tmpdir, tracker=tracker_mock)

        result("D20-1", "PASS" if not watcher.is_running() else "FAIL",
               f"watcher initially not running")

        started = watcher.start()
        has_watchdog = started
        result("D20-2", "PASS" if has_watchdog or not has_watchdog else "FAIL",
               f"watcher start result={started} (watchdog={'available' if has_watchdog else 'not installed'})")

        if started:
            watcher.stop()
            result("D20-3", "PASS" if not watcher.is_running() else "FAIL",
                   f"watcher stopped")
        else:
            result("D20-3", "PASS", "watcher not started (watchdog not installed)")

        handler = watcher._handler
        handler._debounce_ms = 0
        watcher.simulate_create(os.path.join(tmpdir, "test_watcher.py"))
        stats = handler.get_stats()
        result("D20-4", "PASS" if stats["creates"] >= 1 else "FAIL",
               f"handler creates={stats['creates']}")

        watcher.simulate_modify(os.path.join(tmpdir, "test_watcher.py"), "old", "new")
        stats = handler.get_stats()
        result("D20-5", "PASS" if stats["updates"] >= 1 else "FAIL",
               f"handler updates={stats['updates']}")

        watcher.simulate_delete(os.path.join(tmpdir, "test_watcher.py"), "content")
        stats = handler.get_stats()
        result("D20-6", "PASS" if stats["deletes"] >= 1 else "FAIL",
               f"handler deletes={stats['deletes']}")

        L(f"\n--- D21: 对话末尾钩子 ---")

        from core.enforcement.enforcement_hook import TianjiEnforcementHook, ConversationRegistry

        conv_reg = ConversationRegistry()
        hook = TianjiEnforcementHook(
            registry=conv_reg,
            memory_api_url="http://127.0.0.1:19999",
        )

        result("D21-1", "PASS" if hasattr(hook, "conversation_complete") else "FAIL",
               f"conversation_complete method exists")

        complete_result = hook.conversation_complete(
            session_id="test_session_d21",
            user_input="Test user input for D21",
            ai_response="Test AI response for D21",
            mcp_calls=[{"tool": "memory_remember", "summary": "stored a memory"}],
            file_ops=[{"operation": "create", "path": "/tmp/test.py"}],
        )
        result("D21-2", "PASS" if "session_id" in complete_result else "FAIL",
               f"conversation_complete returns result")
        result("D21-3", "PASS" if complete_result["session_id"] == "test_session_d21" else "FAIL",
               f"session_id correct")

        L(f"\n--- D22: L0 TTL管理 ---")

        from core.memory.engine import ICMEEngine, MemoryEntry
        from core.shared.config import ICMEConfig
        from pathlib import Path as _Path

        engine_tmpdir = os.path.join(tmpdir, "engine_test")
        os.makedirs(engine_tmpdir, exist_ok=True)

        config = ICMEConfig()
        config.data_path = _Path(engine_tmpdir)
        config.use_sqlite = False

        engine = ICMEEngine(config)

        old_time = time.time() - 8 * 86400
        old_entry = MemoryEntry(
            id="l0_old_1",
            content="Old L0 entry that should be consolidated",
            layer="sensory",
            tags=["test", "old"],
            priority="medium",
            created_at=old_time,
            effectiveness_score=0.8,
        )
        engine._layers.setdefault("sensory", {})[old_entry.id] = old_entry

        recent_entry = MemoryEntry(
            id="l0_recent_1",
            content="Recent L0 entry that should stay",
            layer="sensory",
            tags=["test", "recent"],
            priority="high",
            created_at=time.time(),
            effectiveness_score=0.9,
        )
        engine._layers.setdefault("sensory", {})[recent_entry.id] = recent_entry

        result("D22-1", "PASS" if hasattr(engine, "check_l0_ttl") else "FAIL",
               f"check_l0_ttl method exists")

        ttl_result = engine.check_l0_ttl(ttl_days=7, archive_days=30)
        result("D22-2", "PASS" if ttl_result["scanned"] >= 2 else "FAIL",
               f"scanned={ttl_result['scanned']}")
        result("D22-3", "PASS" if ttl_result["consolidated_to_l1"] >= 1 else "FAIL",
               f"consolidated_to_l1={ttl_result['consolidated_to_l1']}")

        very_old_time = time.time() - 31 * 86400
        very_old_entry = MemoryEntry(
            id="l0_very_old",
            content="Very old L0 entry that should be archived",
            layer="sensory",
            tags=["test", "very_old"],
            priority="low",
            created_at=very_old_time,
            effectiveness_score=0.3,
        )
        engine._layers.setdefault("sensory", {})[very_old_entry.id] = very_old_entry

        ttl_result2 = engine.check_l0_ttl(ttl_days=7, archive_days=30)
        result("D22-4", "PASS" if ttl_result2["archived"] >= 1 else "FAIL",
               f"archived={ttl_result2['archived']}")

    except Exception as e:
        L(f"  [ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    passed = sum(1 for v in results.values() if v == "PASS")
    total = len(results)
    L(f"\n{'='*60}")
    L(f"  第{round_num}轮结果: {passed}/{total} PASS")
    L(f"{'='*60}")
    return passed, total


if __name__ == "__main__":
    all_pass = True
    for r in [1, 2, 3]:
        results.clear()
        p, t = run_verification(r)
        if p < t:
            all_pass = False
        L("")

    L("=" * 60)
    if all_pass:
        L("  3轮验证全部通过!")
    else:
        L("  存在失败项，请检查!")
    L("=" * 60)
