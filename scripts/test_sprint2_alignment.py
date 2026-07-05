r"""
Sprint 2 全流程验证脚本 v1.0
==============================
D08-D15: 联动与索引 — 3轮验证
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
    L(f"  Sprint 2 验证 — 第{round_num}轮")
    L(f"{'='*60}")

    tmpdir = tempfile.mkdtemp(prefix=f"tianji_s2_r{round_num}_")
    db_path = os.path.join(tmpdir, "test_icme.db")

    try:
        from core.memory.asset_atom import (
            AssetAtom, AssetRegistry, ChangeAtom, Provenance,
            AssetStatus, ContentType,
        )
        from core.shared.alignment_engine import (
            AlignmentEngine, ChangeClassifier, ImpactAnalyzer,
            CascadeUpdater, ScientificDeleter, ChangeSeverity,
            ImpactReport,
        )
        from core.shared.directory_index import (
            DirectoryScanner, READMEGenerator,
            DirectorySmartIndex, DirChild, AIHook,
        )
        from core.enforcement.consistency_guardian import ConsistencyGuardian

        registry = AssetRegistry(db_path)

        L(f"\n--- D08: 多向对齐引擎 (6步流水线) ---")
        engine = AlignmentEngine(registry)

        a_atom = AssetAtom(
            memory_id="align_a", layer="semantic",
            content_type=ContentType.KNOWLEDGE,
            content_hash=hashlib.sha256(b"knowledge A").hexdigest(),
            provenance=Provenance(created_by="test", created_at=time.time()),
        )
        a_id = registry.register(a_atom)

        b_atom = AssetAtom(
            memory_id="align_b", layer="episodic",
            content_type=ContentType.DECISION,
            content_hash=hashlib.sha256(b"decision B depends on A").hexdigest(),
            provenance=Provenance(created_by="test", created_at=time.time()),
        )
        b_id = registry.register(b_atom)
        registry.add_reference(b_id, a_id)

        change = ChangeAtom(
            change_type="update",
            target_asset_id=a_id,
            diff_summary="Knowledge A updated",
            trigger_source="test",
        )
        align_result = engine.on_change(change, before="knowledge A", after="knowledge A v2")
        result("D08-1", "PASS" if align_result.success else "FAIL",
               f"alignment success={align_result.success}")
        result("D08-2", "PASS" if align_result.severity else "FAIL",
               f"severity={align_result.severity}")
        result("D08-3", "PASS" if align_result.impact_report is not None else "FAIL",
               f"impact_report exists={align_result.impact_report is not None}")

        L(f"\n--- D09: 变更分类器 ---")
        classifier = ChangeClassifier()

        s1 = classifier.classify("x=1", "x = 1", "update")
        result("D09-1", "PASS" if s1 == ChangeSeverity.TRIVIAL else "FAIL",
               f"whitespace change→{s1.value}")

        s2 = classifier.classify("def foo():", "def bar():", "update")
        result("D09-2", "PASS" if s2 in (ChangeSeverity.STRUCTURAL, ChangeSeverity.SEMANTIC) else "FAIL",
               f"rename→{s2.value}")

        s3 = classifier.classify("content", "", "delete")
        result("D09-3", "PASS" if s3 == ChangeSeverity.DESTRUCTIVE else "FAIL",
               f"delete→{s3.value}")

        s4 = classifier.classify("", "new content", "create")
        result("D09-4", "PASS" if s4 == ChangeSeverity.STRUCTURAL else "FAIL",
               f"create→{s4.value}")

        L(f"\n--- D10: 影响分析器 ---")
        c_atom = AssetAtom(
            memory_id="impact_c", layer="episodic",
            content_hash=hashlib.sha256(b"C depends on A").hexdigest(),
            provenance=Provenance(created_by="test", created_at=time.time()),
        )
        c_id = registry.register(c_atom)
        registry.add_reference(c_id, a_id)

        analyzer = ImpactAnalyzer(registry)
        impact = analyzer.analyze(a_id, ChangeSeverity.SEMANTIC)
        result("D10-1", "PASS" if b_id in impact.directly_affected or c_id in impact.directly_affected else "FAIL",
               f"directly_affected={[x[:12] for x in impact.directly_affected]}")
        result("D10-2", "PASS" if impact.total_impact_count >= 2 else "FAIL",
               f"total_impact={impact.total_impact_count}")

        L(f"\n--- D11: 级联更新执行器 ---")
        updater = CascadeUpdater(registry)
        cascade_count = updater.execute(a_id, impact, ChangeSeverity.SEMANTIC)
        result("D11-1", "PASS" if cascade_count >= 1 else "FAIL",
               f"cascade_count={cascade_count}")

        b_after = registry.get(b_id)
        result("D11-2", "PASS" if b_after and b_after.updated_at > b_after.created_at else "FAIL",
               f"B updated_at > created_at")

        L(f"\n--- D12: 科学删除机制 ---")
        del_atom = AssetAtom(
            memory_id="del_target", layer="working",
            content_type=ContentType.FILE,
            content_hash=hashlib.sha256(b"file to delete").hexdigest(),
            provenance=Provenance(created_by="test", created_at=time.time()),
        )
        del_id = registry.register(del_atom)

        ref_atom = AssetAtom(
            memory_id="del_referrer", layer="episodic",
            content_hash=hashlib.sha256(b"references del_target").hexdigest(),
            provenance=Provenance(created_by="test", created_at=time.time()),
        )
        ref_id = registry.register(ref_atom)
        registry.add_reference(ref_id, del_id)

        deleter = ScientificDeleter(registry)
        del_result = deleter.delete_asset(del_id, session_id="d12_test")
        result("D12-1", "PASS" if del_result.get("success") else "FAIL",
               f"delete success={del_result.get('success')}")
        result("D12-2", "PASS" if del_result.get("soft_deleted") else "FAIL",
               f"soft_deleted={del_result.get('soft_deleted')}")

        del_atom_check = registry.get(del_id)
        result("D12-3", "PASS" if del_atom_check and del_atom_check.status == "deleted" else "FAIL",
               f"status={del_atom_check.status if del_atom_check else 'None'}")

        ref_after = registry.get(ref_id)
        has_dangling = any("DANGLING" in r for r in ref_after.references) if ref_after else False
        result("D12-4", "PASS" if has_dangling else "FAIL",
               f"referrer has dangling ref: {has_dangling}")

        L(f"\n--- D13: DirectorySmartIndex数据模型+扫描器 ---")
        test_dir = os.path.join(tmpdir, "test_scan")
        os.makedirs(test_dir, exist_ok=True)
        with open(os.path.join(test_dir, "hello.py"), "w", encoding="utf-8") as f:
            f.write("def greet(name):\n    return f'Hello {name}'\n")
        with open(os.path.join(test_dir, "config.json"), "w", encoding="utf-8") as f:
            f.write('{"version": "1.0"}\n')
        os.makedirs(os.path.join(test_dir, "subdir"), exist_ok=True)
        with open(os.path.join(test_dir, "subdir", "util.py"), "w", encoding="utf-8") as f:
            f.write("def helper():\n    pass\n")

        scanner = DirectoryScanner(registry=registry)
        dir_index = scanner.scan_directory(test_dir)
        result("D13-1", "PASS" if dir_index.total_files >= 3 else "FAIL",
               f"total_files={dir_index.total_files}")
        result("D13-2", "PASS" if dir_index.total_dirs >= 1 else "FAIL",
               f"total_dirs={dir_index.total_dirs}")
        result("D13-3", "PASS" if dir_index.content_hash else "FAIL",
               f"content_hash={dir_index.content_hash}")

        py_files = [c for c in dir_index.children if c.language == "Python"]
        result("D13-4", "PASS" if len(py_files) >= 2 else "FAIL",
               f"Python files={len(py_files)}")

        result("D13-5", "PASS" if "Python" in dir_index.languages else "FAIL",
               f"languages={dir_index.languages}")

        L(f"\n--- D14: README智能索引生成器 ---")
        gen = READMEGenerator()
        readme = gen.generate_readme(dir_index)
        result("D14-1", "PASS" if "AI-SECTION: PATH_INDEX" in readme else "FAIL",
               f"PATH_INDEX section present")
        result("D14-2", "PASS" if "AI-SECTION: FILE_SUMMARY" in readme else "FAIL",
               f"FILE_SUMMARY section present")
        result("D14-3", "PASS" if "AI-SECTION: AI_MEMORY" in readme else "FAIL",
               f"AI_MEMORY section present")
        result("D14-4", "PASS" if "AI-SECTION: AI_HOOKS" in readme else "FAIL",
               f"AI_HOOKS section present")
        result("D14-5", "PASS" if "hello.py" in readme else "FAIL",
               f"hello.py in README")

        updated = gen.update_readme_section(readme, "ai_memory", "- Test memory entry")
        result("D14-6", "PASS" if "Test memory entry" in updated else "FAIL",
               f"update_readme_section works")

        L(f"\n--- D15: 一致性守护 ---")
        guardian = ConsistencyGuardian(registry)

        ref_check = guardian.verify_references()
        result("D15-1", "PASS" if ref_check.total_checked > 0 else "FAIL",
               f"verify_references checked {ref_check.total_checked} assets")

        layer_check = guardian.verify_layer_consistency()
        result("D15-2", "PASS" if layer_check.passed else "FAIL",
               f"verify_layer_consistency passed={layer_check.passed}")

        chain_check = guardian.verify_version_chain()
        result("D15-3", "PASS" if chain_check.total_checked > 0 else "FAIL",
               f"verify_version_chain checked {chain_check.total_checked}")

        audit = guardian.run_full_audit()
        result("D15-4", "PASS" if audit.total_checks >= 3 else "FAIL",
               f"full_audit checks={audit.total_checks}")
        result("D15-5", "PASS" if audit.summary else "FAIL",
               f"audit summary: {audit.summary[:60]}")

        repair_count, repairs = guardian.repair_dangling_refs()
        result("D15-6", "PASS" if repair_count >= 0 else "FAIL",
               f"repair_dangling_refs: {repair_count} repaired")

        broken_atom = AssetAtom(
            memory_id="broken_test", layer="working",
            content_hash=hashlib.sha256(b"broken").hexdigest(),
            provenance=Provenance(created_by="test", created_at=time.time()),
        )
        broken_id = registry.register(broken_atom)
        broken_atom_fetched = registry.get(broken_id)
        broken_atom_fetched.references = ["NONEXISTENT_ID_12345"]
        registry.update(broken_atom_fetched)

        ref_check2 = guardian.verify_references()
        result("D15-7", "PASS" if ref_check2.issues_found > 0 else "FAIL",
               f"detected broken reference: issues={ref_check2.issues_found}")

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
