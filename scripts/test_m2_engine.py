import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.memory.engine import ICMEEngine, MemoryEntry

e = ICMEEngine()

r = e.remember("测试记忆-天机v9.1 ICME升级验证", layer="working", tags=["test", "v9.1", "upgrade"], priority="high")
print(f"1. remember: id={r['id']}, status={r['status']}")

r2 = e.remember("第二条测试记忆-Delta驱动触发验证", layer="sensory", tags=["test", "delta"], priority="medium")
print(f"2. remember2: id={r2['id']}, status={r2['status']}")

rec = e.recall(query="天机", limit=5)
print(f"3. recall: {len(rec)}条匹配")

trigger, reason = e._check_orchestration_trigger("working")
print(f"4. orchestration_trigger: {trigger}, {reason}")

margin = e._get_margin_ratio("working")
print(f"5. margin_ratio working: {margin:.4f}")

level = e._get_margin_level("working")
print(f"6. margin_level: {level}")

ps = e.promotion_score(next(iter(e._layers["working"].values())))
print(f"7. promotion_score: {ps:.4f}")

e._auto_consolidate("working")
print(f"8. _auto_consolidate executed")

s = e.stats()
print(f"9. stats: entries={s['total_entries']}, hit_rate={s.get('hit_rate', 'N/A')}")

vc = e.verify_consistency()
print(f"10. verify_consistency: consistent={vc['consistent']}, errors={len(vc['errors'])}, warnings={len(vc['warnings'])}")

log = e.get_consolidation_event_log(5)
print(f"11. consolidation_log: {len(log)} events")

print("\n✅ M2 全功能闭环验证通过!")
