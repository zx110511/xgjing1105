r"""
天机L3 Episodic异常模式写入器
==============================
将Phase2审计中发现的"影子字段"和"枚举假设"两大异常模式
写入天机L3 Episodic记忆层，供未来进化闭环参考。
"""
import urllib.request
import json
import time
from datetime import datetime

BASE_URL = "http://127.0.0.1:8771"

SHADOW_FIELD_PATTERN = {
    "content": json.dumps({
        "pattern_name": "影子字段",
        "pattern_id": "anomaly-001",
        "category": "dataclass_field_mismatch",
        "layer": "episodic",
        "severity": "CRITICAL",
        "discovered_in": "Phase2 集成审计",
        "discovered_date": "2026-05-24",
        "description": "代码中使用了dataclass不存在的字段名，导致AttributeError。因Python dataclass不进行编译期字段检查，IDE和类型检查器无法发现此类错误，形成'影子字段'——看似存在实则不存在的字段引用。",
        "root_cause": (
            "1. 开发者基于假设而非实际dataclass定义来引用字段\n"
            "2. Python dataclass无编译期字段验证\n"
            "3. 缺乏自动化字段验证机制"
        ),
        "symptoms": [
            "AttributeError: 'XxxClass' object has no attribute 'yyy_field'",
            "NoneType从空字段传递导致后续TypeError",
            "测试覆盖不足导致运行时才发现",
        ],
        "concrete_cases": [
            {"bug": "Bug#8", "field": "dependencies 引用为 deps", "file": "governance_orchestrator.py"},
            {"bug": "Bug#9", "field": "circular_dependencies vs circular_deps", "file": "static_analyzer.py"},
            {"bug": "Bug#10", "field": "total_edges vs total_deps", "file": "static_analyzer.py"},
            {"bug": "Bug#11", "field": "overall_verdict vs audit_verdict", "file": "governance_pipeline.py"},
            {"bug": "Bug#12", "field": "source_module 缺失", "file": "module_registry.py"},
        ],
        "fix_strategy": (
            "1. 所有dataclass字段引用前必须由字段验证脚本确认\n"
            "2. 编写dataclass字段验证规范（已沉淀到科研区）\n"
            "3. 在CI/CD中集成字段名检查\n"
            "4. 使用dataclasses.fields() 在运行时验证"
        ),
        "prevention_measure": (
            "引入dclass_field_validator.py自动化验证脚本\n"
            "在模块注册前对TianjiModuleDefinition进行字段完整性检查\n"
            "静态分析阶段加入字段引用验证规则"
        ),
    }, ensure_ascii=False),
    "layer": "episodic",
    "tags": ["anomaly-pattern", "shadow-field", "dataclass", "governance", "Phase2"],
    "importance": 0.95,
    "timestamp": time.time(),
    "source": "Phase2-SSS-Audit",
}

ENUM_ASSUMPTION_PATTERN = {
    "content": json.dumps({
        "pattern_name": "枚举假设",
        "pattern_id": "anomaly-002",
        "category": "enum_value_assumption",
        "layer": "episodic",
        "severity": "CRITICAL",
        "discovered_in": "Phase2 集成审计",
        "discovered_date": "2026-05-24",
        "description": "开发者基于对枚举类值的假设使用字符串字面量而非枚举成员，导致运行时枚举验证失败。当枚举.search()或.enum()收到不存在的字符串值时，无法匹配到任何枚举成员。",
        "root_cause": (
            "1. 开发者假定枚举值而不查阅实际枚举定义\n"
            "2. 字符串字面量比枚举引用更易编写但缺乏编译期检查\n"
            "3. 枚举类定义分散在多个文件，查找成本高"
        ),
        "symptoms": [
            "ValueError: 'xxx' is not a valid EnumName",
            "枚举.search()返回None导致后续代码崩溃",
            "使用字符串 'active' 代替 ModuleLifecycleState.ACTIVE",
        ],
        "concrete_cases": [
            {"bug": "Bug#4", "enum": "ModuleLifecycleState 'active' vs ModuleLifecycleState.ACTIVE", "file": "governance_pipeline.py"},
            {"bug": "Bug#5", "enum": "AuditStatus 不存在值", "file": "module_registry.py"},
            {"bug": "Bug#6", "enum": "AuditVerdict 不存在值", "file": "governance_pipeline.py"},
            {"bug": "Bug#7", "enum": "ApprovalLevel 不存在值", "file": "governance_pipeline.py"},
        ],
        "fix_strategy": (
            "1. 所有状态/类型字段必须使用枚举成员而非字符串\n"
            "2. 在代码审查中强制执行枚举使用检查\n"
            "3. 编写枚举验证脚本，扫描代码中的字符串枚举使用\n"
            "4. 在模块注册时使用enum.search()进行双向验证"
        ),
        "prevention_measure": (
            "在静态分析器中添加'枚举使用合规性'验证规则\n"
            "GovernancePipeline的update_state方法仅接受枚举类型参数\n"
            "审计阶段检测所有直接使用字符串枚举的代码"
        ),
    }, ensure_ascii=False),
    "layer": "episodic",
    "tags": ["anomaly-pattern", "enum-assumption", "enum", "governance", "Phase2"],
    "importance": 0.95,
    "timestamp": time.time(),
    "source": "Phase2-SSS-Audit",
}


def store_episodic_memory(data: dict) -> bool:
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/api/memory/",
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        r = urllib.request.urlopen(req, timeout=5)
        result = json.loads(r.read().decode("utf-8"))
        print(f"  ✅ 写入成功: {result.get('entry_id', '?')}")
        return True
    except urllib.error.HTTPError as e:
        print(f"  ❌ HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}")
        return False
    except Exception as e:
        print(f"  ❌ {e}")
        return False


def check_service() -> bool:
    try:
        urllib.request.urlopen(f"{BASE_URL}/api/health", timeout=3)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("  天机L3 Episodic层 — 异常模式写入")
    print("=" * 60)

    if not check_service():
        print("\n⚠️ 天机服务未运行，尝试直接写入记忆引擎...\n")

    print("\n📝 写入异常模式: '影子字段' (anomaly-001)")
    ok1 = store_episodic_memory(SHADOW_FIELD_PATTERN)

    print("\n📝 写入异常模式: '枚举假设' (anomaly-002)")
    ok2 = store_episodic_memory(ENUM_ASSUMPTION_PATTERN)

    print("\n" + "=" * 60)
    print(f"  结果: {'✅ 全部写入成功' if ok1 and ok2 else '⚠️ 部分写入失败'}")
    print(f"  时间: {datetime.now().isoformat()}")
    print("=" * 60)
