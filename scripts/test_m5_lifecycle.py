import sys
import tempfile
import json
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

print("=== M5 审计4.1: 语法导入 ===")
from core.shared.skill_registry import (
    SkillRegistry, SkillLifecycleTracker, SkillPhase, SkillEvent,
    SkillSchema, SkillCategory, SkillStatus,
)
print("✅ v1.2 全部类导入成功 (含SkillLifecycleTracker)")

print("\n=== 审计4.2: SkillPhase 六阶段枚举 ===")
for p in SkillPhase:
    print(f"   {p.name}: {p.value}")
assert len(list(SkillPhase)) == 6
print("✅ 6阶段生命周期: CREATED/VALIDATED/REUSED/OPTIMIZED/DEPRECATED/REMOVED")

print("\n=== 审计4.3: SkillEvent dataclass ===")
evt = SkillEvent(
    skill_name="test-skill",
    phase=SkillPhase.CREATED,
    agent_id="miaobi",
    details={"version": "0.1.0"},
)
d = evt.to_dict()
print(f"   event_id={d['event_id']}, skill={d['skill_name']}, phase={d['phase']}")
assert d['skill_name'] == "test-skill"
assert d['phase'] == "created"
assert d['agent_id'] == "miaobi"
assert d['details']['version'] == "0.1.0"
print("✅ SkillEvent 字段完整 + JSON序列化")

print("\n=== 审计4.4: track_event 事件记录 ===")
tracker = SkillLifecycleTracker()
e1 = tracker.track_event("s1", SkillPhase.CREATED, "a1")
e2 = tracker.track_event("s1", SkillPhase.VALIDATED, "a2")
e3 = tracker.track_event("s2", SkillPhase.REUSED, "a3")
e4 = tracker.track_event("s3", SkillPhase.DEPRECATED)

stats = tracker.get_stats()
print(f"   total_events={stats['total_events']}, created={stats['created']}, validated={stats['validated']}")
print(f"   reused={stats['reused']}, deprecated={stats['deprecated']}")
assert stats['total_events'] == 4
assert stats['created'] == 1
assert stats['validated'] == 1
assert stats['reused'] == 1
assert stats['deprecated'] == 1
print("✅ track_event 6阶段计数准确")

print("\n=== 审计4.5: get_events 过滤查询 ===")
all_evts = tracker.get_events(limit=100)
print(f"   all events: {len(all_evts)}")
assert len(all_evts) == 4

s1_evts = tracker.get_events(skill_name="s1")
print(f"   s1 events: {len(s1_evts)}")
assert len(s1_evts) == 2

created_evts = tracker.get_events(phase=SkillPhase.CREATED)
print(f"   CREATED events: {len(created_evts)}")
assert len(created_evts) == 1
print("✅ get_events 支持 skill_name + phase 双过滤")

print("\n=== 审计4.6: _persist_event + _replay_audit_log ===")
import shutil
tmp_dir = Path(tempfile.mkdtemp())
try:
    tracker2 = SkillLifecycleTracker(skills_dir=tmp_dir)
    tracker2.track_event("s-replay", SkillPhase.OPTIMIZED, "a1", {"v": "1.0"})
    tracker2.track_event("s-replay", SkillPhase.DEPRECATED, "a2")

    tracker3 = SkillLifecycleTracker(skills_dir=tmp_dir)
    replayed = tracker3._replay_audit_log()
    print(f"   replayed events: {replayed}")
    assert replayed >= 2
    stats3 = tracker3.get_stats()
    print(f"   after replay: total_events_in_memory={stats3['total_events_in_memory']}")
    assert stats3['total_events_in_memory'] >= 2
    print("✅ JSONL持久化 + 审计回放")
finally:
    shutil.rmtree(tmp_dir, ignore_errors=True)

print("\n=== 审计4.7: _scan_skill_files + detect_changes ===")
tmp_dir2 = Path(tempfile.mkdtemp())
try:
    tracker4 = SkillLifecycleTracker(skills_dir=tmp_dir2)

    s1_dir = tmp_dir2 / "skill-alpha"
    s1_dir.mkdir()
    (s1_dir / "SKILL.md").write_text("---\ndescription: test\n---\n# Alpha", encoding="utf-8")
    time.sleep(0.1)

    changes = tracker4.detect_changes()
    print(f"   first scan: {len(changes)} events")
    for c in changes:
        print(f"     {c.phase.value}: {c.skill_name}")

    created_evts = [c for c in changes if c.phase == SkillPhase.CREATED]
    assert len(created_evts) >= 1
    print("   ✅ 新文件→CREATED")

    time.sleep(0.1)
    (s1_dir / "SKILL.md").write_text("---\ndescription: updated\n---\n# Alpha v2", encoding="utf-8")
    changes2 = tracker4.detect_changes()
    print(f"   second scan: {len(changes2)} events")
    opt_evts = [c for c in changes2 if c.phase == SkillPhase.OPTIMIZED]
    assert len(opt_evts) >= 1
    print("   ✅ mtime变更→OPTIMIZED")

    import shutil as sh
    sh.rmtree(s1_dir)
    changes3 = tracker4.detect_changes()
    print(f"   third scan (after delete): {len(changes3)} events")
    rem_evts = [c for c in changes3 if c.phase == SkillPhase.REMOVED]
    assert len(rem_evts) >= 1
    print("   ✅ 目录删除→REMOVED")

    s4_stats = tracker4.get_stats()
    print(f"   scans_completed: {s4_stats['scans_completed']}")
    assert s4_stats['scans_completed'] == 3
    print("   ✅ scans_completed=3")
finally:
    import shutil as sh
    sh.rmtree(tmp_dir2, ignore_errors=True)

print("\n=== 审计4.8: CausalPairRecorder 集成 ===")
from core.processors.evolution_loop import CausalPairRecorder
rec = CausalPairRecorder()
tracker5 = SkillLifecycleTracker(recorder=rec)
tracker5.track_event("s-rec", SkillPhase.VALIDATED, "a1")
tracker5.track_event("s-rec", SkillPhase.REUSED, "a2")
rec_stats = rec.get_stats()
print(f"   recorder total_pairs: {rec_stats['total_pairs']} (expected 2)")
assert rec_stats['total_pairs'] >= 2
print("✅ track_event 自动喂入 CausalPairRecorder")

print("\n=== 审计4.9: 集成验证 ===")
from server.main import app
import_time = time.time()
print(f"   main.py 导入成功: {len(app.routes)} routes")
assert len(app.routes) >= 100

print(f"\n✅ M5 SkillLifecycleTracker 三级审计全部通过!")
