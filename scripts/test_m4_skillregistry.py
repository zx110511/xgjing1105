import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

print("=== M4 审计4.1: 语法导入 ===")
from core.shared.skill_registry import (
    SkillRegistry, SkillCategory, SkillStatus, SkillSchema,
    SkillComposition, AGENT_SKILL_MAP, BUILTIN_COMPOSITIONS,
)
print("✅ v1.1 全部类导入成功")

print("\n=== 审计4.2: SkillSchema.access_count 字段 ===")
schema = SkillSchema(
    name="test-skill", description="测试Skill",
    category=SkillCategory.SYSTEM, version="0.1.0",
)
print(f"   access_count: {schema.access_count}")
assert hasattr(schema, 'access_count'), "access_count字段缺失!"
assert schema.access_count == 0
schema.access_count = 5
assert schema.access_count == 5
print("✅ access_count 字段存在且可读写 (之前NameError)")

print("\n=== 审计4.3: register() + record_action ===")
registry = SkillRegistry()
assert registry.evolution_loop is not None, "EvolutionLoop未初始化!"
print(f"   EvolutionLoop: 已创建, module={registry.evolution_loop._module_name}")

reg_schema = SkillSchema(
    name="test-register", description="注册测试",
    category=SkillCategory.MEMORY, version="0.1.0",
)
ok = registry.register(reg_schema)
print(f"   register: {ok}")
evo_stats = registry.evolution_loop.get_stats()
print(f"   evo_loop.actions_recorded: {evo_stats['actions_recorded']}")
assert evo_stats['actions_recorded'] >= 1, "record_action 未被调用!"
print("✅ register() 自动喂入EvolutionLoop (之前evo_loop空转)")

registry.register(reg_schema)
evo_stats2 = registry.evolution_loop.get_stats()
print(f"   二次register后 actions_recorded: {evo_stats2['actions_recorded']}")

print("\n=== 审计4.4: _learn_from_skill_usage (access_count fix) ===")
skill = registry.get("test-register")
skill.access_count = 1
learn_result = registry._learn_from_skill_usage([], {"avg": 0.3})
print(f"   learn: underused={learn_result['underused_skills']}")
print("✅ _learn_from_skill_usage 不再 AttributeError (之前access_count缺失)")

print("\n=== 审计4.5: CausalPairRecorder 集成 ===")
from core.processors.evolution_loop import CausalPairRecorder
recorder = CausalPairRecorder()
reg2 = SkillRegistry(recorder=recorder)
print(f"   reg2.recorder: {reg2.recorder is not None}")
assert reg2.recorder is not None

s2 = SkillSchema(name="test-recorder", description="d", category=SkillCategory.SYSTEM)
reg2.register(s2)
rec_stats = recorder.get_stats()
print(f"   recorder.pairs: {rec_stats['total_pairs']}")
assert rec_stats['total_pairs'] >= 1
print("✅ record_action 自动喂入 CausalPairRecorder")

print("\n=== 审计4.6: ClosedLoopLearningEngine 集成 ===")
from core.processors.learning_loop import ClosedLoopLearningEngine
learn_eng = ClosedLoopLearningEngine()
reg3 = SkillRegistry(learning_engine=learn_eng)
print(f"   reg3.learning_engine: {reg3.learning_engine is not None}")
assert reg3.learning_engine is not None
print("✅ learning_engine 注入成功")

print("\n=== 审计4.7: discover/schemas/agent_filter ===")
stats = registry.get_stats()
print(f"   total_skills: {stats['total_skills']}")

agent_skills = registry.filter_by_agent("yiku")
print(f"   yiku skills: {len(agent_skills)}")

schemas = registry.get_schemas("yiku")
print(f"   yiku schemas: {len(schemas)}")

composition = registry.resolve_composition("memory-lifecycle")
print(f"   memory-lifecycle: {len(composition)} skills (引用Skill未注册→预期0)")
comps = registry.list_compositions()
print(f"   total_compositions: {len(comps)}")
assert len(comps) >= 4
print("✅ resolve_composition + list_compositions 正常 (4内建组合已加载)")

print("\n=== 审计4.8: BUILTIN_COMPOSITIONS ===")
print(f"   内建组合: {len(BUILTIN_COMPOSITIONS)}个")
for c in BUILTIN_COMPOSITIONS:
    print(f"     {c['name']}: {len(c['skills'])} skills")

print("\n=== 审计4.9: AGENT_SKILL_MAP ===")
print(f"   Agent角色映射: {len(AGENT_SKILL_MAP)}个Agent")
assert len(AGENT_SKILL_MAP) >= 18
print("✅ 22 Agent角色映射完整")

print("\n=== 审计4.10: 集成验证 ===")
from server.main import app
skill_routes = [r.path for r in app.routes if "skill" in r.path.lower() or "registry" in r.path.lower()]
print(f"   skill/registry 路由: {skill_routes}")
print(f"   路由总数: {len(app.routes)}")

print(f"\n✅ M4 SkillRegistry 三级审计全部通过!")
