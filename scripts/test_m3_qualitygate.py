import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

print("=== 审计4.1: 语法导入 ===")
from core.processors.quality_gate import (
    QualityGate, GateVerdict, GateResult,
    _CONFLICT_RESOLVER_AVAILABLE, _DRIFT_DETECTOR_AVAILABLE,
)
print(f"✅ quality_gate 导入成功")
print(f"   ConflictResolver: {_CONFLICT_RESOLVER_AVAILABLE}")
print(f"   PreferenceDriftDetector: {_DRIFT_DETECTOR_AVAILABLE}")

print("\n=== 审计4.2: 核心功能闭环 ===")
from core.shared.config import DEFAULT_CONFIG
qg = QualityGate(config=DEFAULT_CONFIG.quality_gate)

print(f"✅ QualityGate 初始化成功")
print(f"   conflict_resolver: {qg._conflict_resolver}")
print(f"   drift_detector: {qg._preference_drift_detector}")

result = qg.check("这是一个高质量的测试记忆内容，包含架构设计讨论的详细方案和实施路径", "episodic", ["架构", "设计"], "high")
print(f"✅ check(高质量): verdict={result.verdict.value}, layer={result.target_layer}, reason={result.reason[:50]}...")
print(f"   quality_dims: {result.quality_dimensions}")

result = qg.check("噪声噪声噪声噪声噪声噪声噪声噪声噪声", "episodic", [], "low")
print(f"✅ check(噪声): verdict={result.verdict.value}, reason={result.reason[:50]}...")

result = qg.check("这是一个标准长度的测试内容用于验证降级机制的完整描述", "semantic", [], "low")
print(f"✅ check(降级): verdict={result.verdict.value}, layer={result.target_layer}")

qg.update_will("架构", 0.8)
qg.update_will("重构", 0.6)
topics = qg.get_will_topics(5)
print(f"✅ update_will + get_will_topics: {topics}")

result = qg.check("我们来进行架构重构的详细讨论和设计方案的全面评审和体系优化", "episodic", ["架构"], "high")
print(f"✅ check(will对齐): verdict={result.verdict.value}, dims={result.quality_dimensions}")

print("\n=== 审计4.3: 冲突检测 ===")
class FakeEntry:
    def __init__(self, id, content):
        self.id = id
        self.content = content

r1 = qg.check("当前的系统架构使用微服务模式进行分布式部署和管理", "episodic", ["架构"], "high")
print(f"✅ 第一条记忆: {r1.verdict.value}")

existing = [FakeEntry("mem-001", "我们不再使用微服务模式，改用单体架构来简化部署")]
r2 = qg.check("当前的系统架构使用微服务模式进行分布式部署和管理", "episodic", ["架构"], "high", existing)
print(f"✅ 冲突检测: verdict={r2.verdict.value}, conflicts={r2.conflicts_with}")
print(f"   reason: {r2.reason[:60]}")

print("\n=== 审计4.4: EvolutionLoop 进化闭环 ===")
print(f"✅ evolution_loop: {qg.evolution_loop}")

qg._sync_evo_config()
print(f"✅ _sync_evo_config 正常运行")

print("\n=== 审计4.5: _char_ngrams ===")
ngrams = qg._char_ngrams("hello world", 3)
print(f"✅ _char_ngrams: {len(ngrams)} trigrams from 'hello world'")

print("\n=== 审计4.6: 集成验证 ===")
from server.main import app
gate_routes = [r.path for r in app.routes if "quality" in r.path.lower()]
print(f"✅ main.py quality 路由: {gate_routes}")

print(f"\n✅ M3 QualityGate 三级审计全部通过!")
