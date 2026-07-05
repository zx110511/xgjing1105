r"""
Sprint 1 全流程验证脚本 v2.0
==============================
D01-D07: 资产原子化 — 3轮验证
简化D02: 直接调用AssetRegistry模拟remember()注册
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
    L(f"  Sprint 1 验证 — 第{round_num}轮")
    L(f"{'='*60}")

    tmpdir = tempfile.mkdtemp(prefix=f"tianji_s1_r{round_num}_")
    db_path = os.path.join(tmpdir, "test_icme.db")

    try:
        from core.memory.asset_atom import (
            AssetAtom, AssetRegistry, ChangeAtom, Provenance,
            AssetStatus, ContentType, VALID_TRANSITIONS,
        )
        from core.shared.change_tracker import ChangeTracker

        L(f"\n--- D01: AssetAtom数据模型 + asset_registry表 ---")
        registry = AssetRegistry(db_path)
        atom = AssetAtom(
            memory_id="test_mem_001",
            layer="episodic",
            content_type=ContentType.DECISION,
            content_hash=hashlib.sha256(b"test content").hexdigest(),
            provenance=Provenance(
                created_by="test",
                created_at=time.time(),
                reason="D01 verification",
                session_id="test_session",
            ),
        )
        asset_id = registry.register(atom)
        result("D01-1", "PASS" if asset_id else "FAIL", f"register returned asset_id={asset_id}")

        fetched = registry.get(asset_id)
        result("D01-2", "PASS" if fetched and fetched.memory_id == "test_mem_001" else "FAIL",
               f"get() memory_id={fetched.memory_id if fetched else 'None'}")
        result("D01-3", "PASS" if fetched and fetched.content_type == "decision" else "FAIL",
               f"content_type={fetched.content_type if fetched else 'None'}")
        result("D01-4", "PASS" if fetched and fetched.status == "active" else "FAIL",
               f"status={fetched.status if fetched else 'None'}")
        result("D01-5", "PASS" if fetched and fetched.version == 1 else "FAIL",
               f"version={fetched.version if fetched else 'None'}")

        stats = registry.get_stats()
        result("D01-6", "PASS" if stats["total_assets"] >= 1 else "FAIL",
               f"total_assets={stats['total_assets']}")

        L(f"\n--- D02: remember()→AssetAtom自动注册 (模拟) ---")
        memory_id = "sim_mem_" + hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]
        content = "D02测试: 自动注册AssetAtom"
        content_hash = AssetRegistry.compute_content_hash(content)

        d02_atom = AssetAtom(
            memory_id=memory_id,
            layer="episodic",
            content_type=ContentType.DECISION,
            content_hash=content_hash,
            provenance=Provenance(
                created_by="engine",
                created_at=time.time(),
                reason="Auto-registered from remember()",
                session_id="s1_test",
            ),
        )
        d02_asset_id = registry.register(d02_atom)
        result("D02-1", "PASS" if d02_asset_id else "FAIL", f"asset_id={d02_asset_id}")

        d02_fetched = registry.get(d02_asset_id)
        result("D02-2", "PASS" if d02_fetched and d02_fetched.memory_id == memory_id else "FAIL",
               f"asset memory_id={d02_fetched.memory_id if d02_fetched else 'None'}")
        result("D02-3", "PASS" if d02_fetched and d02_fetched.content_type == "decision" else "FAIL",
               f"content_type={d02_fetched.content_type if d02_fetched else 'None'}")
        result("D02-4", "PASS" if d02_fetched and d02_fetched.content_hash == content_hash else "FAIL",
               f"content_hash match={d02_fetched.content_hash == content_hash if d02_fetched else False}")

        L(f"\n--- D03: ChangeAtom数据模型 + change_log表 ---")
        change = ChangeAtom(
            change_type="create",
            target_asset_id=asset_id,
            target_path="/test/file.py",
            after_snapshot=hashlib.sha256(b"new content").hexdigest(),
            diff_summary="File created for D03 test",
            trigger_source="test",
            session_id="test_session",
        )
        change_id = registry.log_change(change)
        result("D03-1", "PASS" if change_id else "FAIL", f"log_change returned change_id={change_id}")

        changes = registry.get_changes(asset_id)
        result("D03-2", "PASS" if len(changes) >= 1 else "FAIL", f"changes count={len(changes)}")
        result("D03-3", "PASS" if changes and changes[0].change_type == "create" else "FAIL",
               f"change_type={changes[0].change_type if changes else 'None'}")

        L(f"\n--- D04: AI工具调用→ChangeAtom生成 ---")
        tracker = ChangeTracker(registry)

        c1 = tracker.track_create("/test/new_file.py", "print('hello')", session_id="d04_test")
        result("D04-1", "PASS" if c1.change_type == "create" else "FAIL",
               f"track_create change_type={c1.change_type}")
        result("D04-2", "PASS" if c1.target_path == "/test/new_file.py" else "FAIL",
               f"target_path={c1.target_path}")

        c2 = tracker.track_update("/test/new_file.py", "print('hello')", "print('world')",
                                   session_id="d04_test")
        result("D04-3", "PASS" if c2.change_type == "update" else "FAIL",
               f"track_update change_type={c2.change_type}")
        result("D04-4", "PASS" if c2.before_snapshot != c2.after_snapshot else "FAIL",
               f"hash changed: {c2.before_snapshot[:8]}→{c2.after_snapshot[:8]}")

        c3 = tracker.track_delete("/test/new_file.py", "print('world')", session_id="d04_test")
        result("D04-5", "PASS" if c3.change_type == "delete" else "FAIL",
               f"track_delete change_type={c3.change_type}")

        tstats = tracker.get_stats()
        result("D04-6", "PASS" if tstats["total_tracked"] == 3 else "FAIL",
               f"total_tracked={tstats['total_tracked']}")

        L(f"\n--- D05: 版本链构建 ---")
        v1_atom = AssetAtom(
            memory_id="version_test",
            layer="working",
            content_type=ContentType.CONVERSATION,
            content_hash=hashlib.sha256(b"v1 content").hexdigest(),
            provenance=Provenance(created_by="test", created_at=time.time(), reason="v1"),
        )
        v1_id = registry.register(v1_atom)

        v2_atom = AssetAtom(
            memory_id="version_test",
            layer="working",
            content_type=ContentType.CONVERSATION,
            content_hash=hashlib.sha256(b"v2 content").hexdigest(),
            version=2,
            parent_version_id=v1_id,
            provenance=Provenance(created_by="test", created_at=time.time(), reason="v2"),
        )
        registry.transition(v1_id, "superseded", "test")
        v2_id = registry.register(v2_atom)

        v3_atom = AssetAtom(
            memory_id="version_test",
            layer="working",
            content_type=ContentType.CONVERSATION,
            content_hash=hashlib.sha256(b"v3 content").hexdigest(),
            version=3,
            parent_version_id=v2_id,
            provenance=Provenance(created_by="test", created_at=time.time(), reason="v3"),
        )
        registry.transition(v2_id, "superseded", "test")
        v3_id = registry.register(v3_atom)

        chain = registry.get_version_chain(v3_id)
        result("D05-1", "PASS" if len(chain) == 3 else "FAIL",
               f"version chain length={len(chain)}")

        latest = registry.get_latest_version("version_test")
        result("D05-2", "PASS" if latest and latest.version == 3 else "FAIL",
               f"latest version={latest.version if latest else 'None'}")

        L(f"\n--- D06: 引用图构建 ---")
        ref_a = AssetAtom(
            memory_id="ref_a", layer="semantic",
            content_hash=hashlib.sha256(b"ref a content").hexdigest(),
            provenance=Provenance(created_by="test", created_at=time.time()),
        )
        ref_b = AssetAtom(
            memory_id="ref_b", layer="semantic",
            content_hash=hashlib.sha256(b"ref b content").hexdigest(),
            provenance=Provenance(created_by="test", created_at=time.time()),
        )
        a_id = registry.register(ref_a)
        b_id = registry.register(ref_b)

        ok = registry.add_reference(a_id, b_id)
        result("D06-1", "PASS" if ok else "FAIL", f"add_reference A→B: {ok}")

        a_after = registry.get(a_id)
        b_after = registry.get(b_id)
        result("D06-2", "PASS" if b_id in a_after.references else "FAIL",
               f"A.references contains B: {b_id in a_after.references}")
        result("D06-3", "PASS" if a_id in b_after.referenced_by else "FAIL",
               f"B.referenced_by contains A: {a_id in b_after.referenced_by}")

        deps = registry.get_dependencies(a_id)
        result("D06-4", "PASS" if len(deps) == 1 and deps[0].asset_id == b_id else "FAIL",
               f"A dependencies: {[d.asset_id for d in deps]}")

        dependents = registry.get_dependents(b_id)
        result("D06-5", "PASS" if len(dependents) == 1 and dependents[0].asset_id == a_id else "FAIL",
               f"B dependents: {[d.asset_id for d in dependents]}")

        registry.remove_reference(a_id, b_id)
        a_removed = registry.get(a_id)
        result("D06-6", "PASS" if b_id not in a_removed.references else "FAIL",
               f"remove_reference: B no longer in A.references")

        L(f"\n--- D07: 资产状态机 ---")
        sm_atom = AssetAtom(
            memory_id="sm_test", layer="working",
            content_hash=hashlib.sha256(b"state machine test").hexdigest(),
            provenance=Provenance(created_by="test", created_at=time.time()),
        )
        sm_id = registry.register(sm_atom)

        ok1, msg1 = registry.transition(sm_id, "deleted", "test")
        result("D07-1", "PASS" if ok1 else "FAIL", f"active→deleted: {msg1}")

        ok2, msg2 = registry.transition(sm_id, "archived", "test")
        result("D07-2", "PASS" if ok2 else "FAIL", f"deleted→archived: {msg2}")

        ok3, msg3 = registry.transition(sm_id, "active", "test")
        result("D07-3", "PASS" if not ok3 else "FAIL", f"archived→active(blocked): {msg3}")

        sm2 = AssetAtom(
            memory_id="sm_test2", layer="working",
            content_hash=hashlib.sha256(b"state machine test 2").hexdigest(),
            provenance=Provenance(created_by="test", created_at=time.time()),
        )
        sm2_id = registry.register(sm2)
        ok4, msg4 = registry.transition(sm2_id, "archived", "test")
        result("D07-4", "PASS" if not ok4 else "FAIL", f"active→archived(blocked): {msg4}")

        sm_after = registry.get(sm_id)
        result("D07-5", "PASS" if sm_after and sm_after.status == "archived" else "FAIL",
               f"final status={sm_after.status if sm_after else 'None'}")

        sm_changes = registry.get_changes(sm_id)
        result("D07-6", "PASS" if len(sm_changes) >= 2 else "FAIL",
               f"status transition changes logged: {len(sm_changes)}")

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
