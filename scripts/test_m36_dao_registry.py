r"""
M36 道谱注册中心 测试脚本 v9.1
============================
测试用例: 36项 (36地煞全量覆盖)
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0

def test(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}  --  {detail}")

from core.shared.dao_registry import (
    DaoRegistry,
    DISHA_REGISTRY,
    TIANGANG_TEMPLATE,
    DAO_NAMES,
    export_registry_json,
    DaoModuleEntry,
)

print("=" * 60)
print("  M36 道谱注册中心 测试 v9.1")
print("=" * 60)

registry = DaoRegistry()

print("\n📋 1. 地煞注册表完整性 (12项)")
test("1.1 地煞总数=36", len(DISHA_REGISTRY) == 36, f"实际{len(DISHA_REGISTRY)}")
test("1.2 道总数=9", len(DAO_NAMES) == 9)
disha_ids = [d["id"] for d in DISHA_REGISTRY]
test("1.3 地煞ID无重复", len(set(disha_ids)) == len(disha_ids))
for i in range(1, 10):
    prefix = f"D{i}-"
    count = sum(1 for did in disha_ids if did.startswith(prefix))
    test(f"1.{i+3} 道{i}地煞数=4", count == 4, f"实际{count}")
test("1.13 D1-1存在", any(d["id"] == "D1-1" for d in DISHA_REGISTRY))
test("1.14 D9-4存在", any(d["id"] == "D9-4" for d in DISHA_REGISTRY))

print("\n🔍 2. query_disha 查询 (5项)")
r = registry.query_disha(disha_id="D1-1")
test("2.1 按ID查询D1-1", len(r) == 1 and r[0]["name"] == "六层引擎煞", f"结果数{len(r)}")
r2 = registry.query_disha(dao_name="道一·记忆体道")
test("2.2 按道查询道一", len(r2) == 4, f"结果数{len(r2)}")
r3 = registry.query_disha(module_id="M1")
test("2.3 按模块查询M1", len(r3) == 1, f"结果数{len(r3)}")
d = registry.get_disha("D5-4")
test("2.4 get_disha D5-4", d is not None and d["name"] == "TVP协议煞")
test("2.5 get_disha 不存在", registry.get_disha("D99-99") is None)

print("\n📊 3. list_disha_by_dao (3项)")
by_dao = registry.list_disha_by_dao()
test("3.1 9道全覆盖", len(by_dao) == 9, f"实际{len(by_dao)}")
test("3.2 每道4地煞", all(len(v) == 4 for v in by_dao.values()))
test("3.3 道一含D1-1~D1-4", all(any(d["id"] == f"D1-{i}" for d in by_dao["道一·记忆体道"]) for i in range(1, 5)))

print("\n☯️ 4. 天罡功能 (3项)")
t = registry.query_tiangang()
test("4.1 天罡模板总数=72", t["total_tiangang"] == 72, f"实际{t['total_tiangang']}")
t1 = registry.query_tiangang(dao_name="道一·记忆体道")
test("4.2 道一天罡=8", t1["total"] == 8, f"实际{t1['total']}")
ok = registry.reserve_tiangang("道一·记忆体道", "T1-1", ["D1-1", "D1-2"])
test("4.3 预留天罡T1-1->2地煞", ok)

print("\n📝 5. register_module (3项)")
ok2 = registry.register_module("M99", "TestModule", "core/test.py", disha_id="D1-1")
test("5.1 动态注册M99", ok2)
mod = registry.get_module("M99")
test("5.2 获取M99", mod is not None and mod.class_name == "TestModule")
list_mods = registry.list_modules()
test("5.3 已注册>36个模块", len(list_mods) >= 37, f"实际{len(list_mods)}")

print("\n💚 6. health (2项)")
h = registry.health()
test("6.1 状态healthy", h["status"] == "healthy", h["status"])
test("6.2 地煞完整", h["disha_complete"] is True)

print("\n🛡️ 7. validate_integrity (2项)")
vi = registry.validate_integrity()
test("7.1 完整性验证通过", vi["valid"] is True, f"问题: {vi['issues']}")
test("7.2 0个问题", len(vi["issues"]) == 0, f"问题: {vi['issues']}")

print("\n📈 8. stats (2项)")
stats = registry.get_stats()
test("8.1 disha=36", stats["total_disha"] == 36)
test("8.2 queries>0", stats["queries_served"] > 0)

print("\n📤 9. export (1项)")
tmp_path = os.path.join(os.path.dirname(__file__), "_test_dao_export.json")
export_registry_json(tmp_path)
test("9.1 导出JSON成功", os.path.exists(tmp_path))
if os.path.exists(tmp_path):
    os.remove(tmp_path)

print("\n🔄 10. tick+EvolutionLoop (1项)")
try:
    registry.tick()
    test("10.1 tick不崩溃", True)
except Exception as e:
    test("10.1 tick不崩溃", False, str(e))

print("\n" + "=" * 60)
print(f"  结果: ✅ {PASS} / ❌ {FAIL} / 总计 {PASS + FAIL}")
print("=" * 60)
sys.exit(0 if FAIL == 0 else 1)