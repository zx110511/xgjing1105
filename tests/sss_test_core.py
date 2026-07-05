import sys
import time
import json
import threading

sys.path.insert(0, r'd:\元初系统\天机v9.1')

results = []

def test(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    results.append(f"{status} {name} {detail}")
    if not condition:
        print(f"  FAIL: {name} — {detail}")

print("=" * 60)
print("  天机 SSS级 核心模块深度测试")
print("=" * 60)

# ============================================================
# M1: ICMEEngine — 六层记忆引擎
# ============================================================
print("\n[M1] ICMEEngine 六层记忆引擎")
from core.memory.engine import ICMEEngine
from core.shared.config import DEFAULT_CONFIG

engine = ICMEEngine(DEFAULT_CONFIG)
test("M1.1 引擎初始化", engine is not None)

stats = engine.stats()
test("M1.2 统计接口", "total_entries" in stats, f"keys={list(stats.keys())[:5]}")

r = engine.remember("核心模块测试-这是一条用于验证ICME引擎完整性的测试数据", layer="working", tags=["core_test"], priority="high")
test("M1.3 写入记忆", r.get("id") is not None, f"id={r.get('id','')}")

entry_id = r.get("id", "")
entries = engine.recall(query="核心模块", limit=5)
test("M1.4 检索记忆", len(entries) > 0, f"count={len(entries)}")

capacity = engine.get_layer_capacity_info()
test("M1.5 层容量信息", isinstance(capacity, dict), f"layers={list(capacity.keys())[:3]}")

success = engine.forget(entry_id)
test("M1.6 删除记忆", success is True)

r2 = engine.remember("短文", layer="working", tags=["short"])
test("M1.7 短内容存储(use_llm=False)", r2.get("status") == "stored", f"status={r2.get('status')}")

# ============================================================
# M2: HybridEngine — SQLite混合引擎
# ============================================================
print("\n[M2] HybridEngine SQLite混合引擎")
from core.memory.hybrid_engine import ICMEStorageEngine

hybrid = ICMEStorageEngine(DEFAULT_CONFIG, use_sqlite=True)
test("M2.1 混合引擎初始化", hybrid is not None)

r = hybrid.remember("SQLite混合引擎测试-验证双后端存储的完整性和可靠性", layer="episodic", tags=["sqlite_test"])
test("M2.2 SQLite写入", r.get("id") is not None, f"id={r.get('id','')}")

sid = r.get("id", "")
entries = hybrid.recall(query="SQLite", limit=5)
test("M2.3 SQLite检索", len(entries) > 0)

hybrid.forget(sid)

# ============================================================
# M3: QualityGate — 质量门禁
# ============================================================
print("\n[M3] QualityGate 质量门禁")
from core.processors.quality_gate import QualityGate

qg = QualityGate(config=DEFAULT_CONFIG.quality_gate, engine=engine)
test("M3.1 质量门禁初始化", qg is not None)

result = qg.check("这是一条足够长的质量门禁测试内容，用于验证质量评估功能是否正常工作", "working", ["test"], "high")
test("M3.2 质量检查-长内容", result is not None)

result2 = qg.check("短", "working", ["test"], "low")
test("M3.3 质量检查-短内容拒绝", result2.verdict.value in ("reject", "downgrade"), f"verdict={result2.verdict.value}")

# ============================================================
# M4: SkillRegistry — 技能自注册
# ============================================================
print("\n[M4] SkillRegistry 技能自注册")
from core.shared.skill_registry import SkillRegistry, SkillSchema, SkillCategory

sr = SkillRegistry()
test("M4.1 技能注册表初始化", sr is not None)

schema = SkillSchema(name="test_skill", description="测试技能", category=SkillCategory.SYSTEM, tags=["test"])
sr.register(schema)
test("M4.2 技能注册", "test_skill" in sr._skills)

skills = sr.list_skills()
test("M4.3 技能列表", len(skills) > 0, f"count={len(skills)}")

sr.unregister("test_skill")
test("M4.4 技能注销", "test_skill" not in sr._skills)

# ============================================================
# M5: EvolutionLoop — 进化闭环
# ============================================================
print("\n[M5] EvolutionLoop 进化闭环")
from core.processors.evolution_loop import EvolutionLoop, LoopPhase

effectiveness_calls = []
learn_calls = []
evolve_calls = []

def mock_effectiveness(action, before, after):
    effectiveness_calls.append(action)
    if action == "bad_action":
        return -0.5
    return 0.3

def mock_learn(causal_pairs, summary):
    learn_calls.append(len(causal_pairs))
    return {"learned": True, "pattern": "test_pattern"}

def mock_evolve(learn_result, config):
    evolve_calls.append(learn_result)
    config["evolved"] = True
    return {"changed": True, "keys": list(config.keys())}

evo = EvolutionLoop(
    module_name="test_module",
    effectiveness_fn=mock_effectiveness,
    learn_fn=mock_learn,
    evolve_fn=mock_evolve,
    mutable_config={"threshold": 0.5},
)
test("M5.1 进化闭环初始化", evo is not None)
test("M5.2 初始阶段IDLE", evo._phase == LoopPhase.IDLE)

evo.record_action("good_action", {"state": "before"}, {"state": "after"})
test("M5.3 记录行动", len(effectiveness_calls) == 1)
test("M5.4 效果计算", effectiveness_calls[0] == "good_action")

evo.record_action("bad_action", {"state": "ok"}, {"state": "bad"})
test("M5.5 负效果累积", evo._urgency > 0, f"urgency={evo._urgency}")

evo.tick()
test("M5.6 tick执行", True)

# ============================================================
# M6: AgentOrchestrator — Agent调度
# ============================================================
print("\n[M6] AgentOrchestrator Agent调度")
from core.orchestration.agent_orchestrator import AgentScheduler, AGENT_CAPABILITY_MATRIX

sched = AgentScheduler()
test("M6.1 调度器初始化", sched is not None)
test("M6.2 版本号", sched.VERSION == "2.0.0-SSS")

summary = sched.get_summary()
test("M6.3 状态摘要", "version" in summary)

tvp = sched.get_tvp_status()
test("M6.4 TVP状态", isinstance(tvp, str) and len(tvp) > 0)

pipeline = sched.create_pipeline("development")
test("M6.5 创建流水线", pipeline is not None)
test("M6.6 流水线阶段数", pipeline.get_stage_count() > 0)

agents = AGENT_CAPABILITY_MATRIX
test("M6.7 Agent能力矩阵", len(agents) > 0, f"count={len(agents)}")

# ============================================================
# M7: LearningLoop — 学习循环
# ============================================================
print("\n[M7] LearningLoop 学习循环")
from core.processors.learning_loop import ClosedLoopLearningEngine

ll = ClosedLoopLearningEngine()
test("M7.1 学习循环初始化", ll is not None)

# ============================================================
# M8: DeepSeekDriver — DeepSeek驾驶者
# ============================================================
print("\n[M8] DeepSeekDriver DeepSeek驾驶者")
try:
    from core.shared.deepseek_driver import DeepSeekDriver, EventBus
    bus = EventBus()
    driver = DeepSeekDriver(event_bus=bus)
    test("M8.1 驾驶者初始化", driver is not None)
    test("M8.2 事件总线", driver.event_bus is bus)
except Exception as e:
    test("M8.1 驾驶者初始化", False, f"error: {str(e)[:80]}")
    test("M8.2 事件总线", False, "跳过")

# ============================================================
# M9: WorkflowEngine — 工作流引擎
# ============================================================
print("\n[M9] WorkflowEngine 工作流引擎")
from core.orchestration.workflow_engine import WorkflowEngine

wf = WorkflowEngine(skill_registry=sr)
test("M9.1 工作流初始化", wf is not None)

# ============================================================
# M10: MessageGateway — 消息网关
# ============================================================
print("\n[M10] MessageGateway 消息网关")
from core.shared.message_gateway import MessageGateway

gw = MessageGateway(skill_registry=sr, workflow_engine=wf)
test("M10.1 消息网关初始化", gw is not None)

# ============================================================
# M11: IntelligentScheduler — 智能调度器
# ============================================================
print("\n[M11] IntelligentScheduler 智能调度器")
from core.orchestration.intelligent_scheduler import TianjiIntelligentScheduler

isch = TianjiIntelligentScheduler()
test("M11.1 智能调度器初始化", isch is not None)

# ============================================================
# M12: EnforcementHook — 强制记录钩子
# ============================================================
print("\n[M12] EnforcementHook 强制记录钩子")
try:
    from core.enforcement.enforcement_hook import TianjiEnforcementHook, ConversationRegistry
    reg = ConversationRegistry()
    hook = TianjiEnforcementHook(registry=reg)
    test("M12.1 钩子初始化", hook is not None)
except Exception as e:
    test("M12.1 钩子初始化", False, f"error: {str(e)[:80]}")

# ============================================================
# M13: LLM集成
# ============================================================
print("\n[M13] LLM集成层")
try:
    from llm_integration import DeepSeekConfig
    cfg = DeepSeekConfig.from_env()
    test("M13.1 DeepSeek配置", cfg is not None)
    test("M13.2 API Key已配置", bool(cfg.api_key), f"has_key={bool(cfg.api_key)}")
except Exception as e:
    test("M13.1 DeepSeek配置", False, f"error: {str(e)[:80]}")
    test("M13.2 API Key已配置", False, "跳过")

# ============================================================
# M14: EmbeddingService — 语义搜索
# ============================================================
print("\n[M14] EmbeddingService 语义搜索")
from indexing.embeddings import EmbeddingService
emb = EmbeddingService(engine)
test("M14.1 嵌入服务初始化", emb is not None)

sr_result = emb.semantic_search("测试", limit=3)
test("M14.2 语义搜索", isinstance(sr_result, list), f"count={len(sr_result)}")

idx_stats = emb.get_index_stats()
test("M14.3 索引统计", isinstance(idx_stats, dict))

# ============================================================
# M15: ActiveMemory — 主动记忆协议
# ============================================================
print("\n[M15] ActiveMemory 主动记忆协议")
try:
    from active_memory.protocol import ActiveMemoryProtocol, ActiveMemoryConfig
    amp = ActiveMemoryProtocol(ActiveMemoryConfig())
    test("M15.1 主动记忆初始化", amp is not None)
except Exception as e:
    test("M15.1 主动记忆初始化", False, f"error: {str(e)[:80]}")

# ============================================================
# M16: Router — 层路由
# ============================================================
print("\n[M16] Router 层路由")
from core.shared.router import LayerRouter
lr = LayerRouter()
test("M16.1 层路由初始化", lr is not None)

# ============================================================
# M17: NamespaceManager — 命名空间管理
# ============================================================
print("\n[M17] NamespaceManager 命名空间管理")
from core.shared.namespace_manager import NamespaceManager
nm = NamespaceManager()
test("M17.1 命名空间初始化", nm is not None)

# ============================================================
# M18: EventBus — 事件总线
# ============================================================
print("\n[M18] EventBus 事件总线")
from core.shared.deepseek_driver import EventBus
eb = EventBus()
test("M18.1 事件总线初始化", eb is not None)

received = []
eb.subscribe("test_event", lambda e: received.append(e))
from core.shared.deepseek_driver import TianjiEvent, EventType
eb.publish(TianjiEvent(event_type=EventType.SYSTEM_STATUS, source="test", payload={"data": "hello"}))
test("M18.2 事件发布/订阅", len(received) > 0)

# ============================================================
# M19: SQLiteStore — SQLite存储
# ============================================================
print("\n[M19] SQLiteStore SQLite存储")
from core.memory.sqlite_store import SQLiteMemoryStore
from pathlib import Path
db_path = Path(r"d:\元初系统\天机v9.1\data\.memory\icme.db")
store = SQLiteMemoryStore(db_path)
test("M19.1 SQLite存储初始化", store is not None)

total_stats = store.get_total_stats()
test("M19.2 存储统计", "total_entries" in total_stats, f"total={total_stats.get('total_entries')}")

# ============================================================
# 汇总
# ============================================================
print()
for r in results:
    print(r)

pass_count = sum(1 for r in results if r.startswith("PASS"))
fail_count = sum(1 for r in results if r.startswith("FAIL"))
print(f"\n{'='*60}")
print(f"  结果: {pass_count} PASS / {fail_count} FAIL / {len(results)} TOTAL")
if fail_count == 0:
    print("  状态: SSS级核心模块测试全部通过!")
else:
    print("  状态: 存在失败项，需要修复")
print(f"{'='*60}")
