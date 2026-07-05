# 天机v9.1 升级完整任务规划 + 执行指令集

> 版本: v3.0 | 日期: 2026-06-03 | 基于84模块/54,704行代码深度审计
> 三遍迭代确认: 第1遍结构设计 → 第2遍缺失环节补全 → 第3遍可执行性验证

---

## 审计基线事实

```
核心模块: 84个Python文件, 54,704行, 2,554函数, 506类
单元测试覆盖: 8.3% (7/84模块)
Docstring缺失: 53.6% (1,369/2,554)
D级模块: 43/84 (51.2%)
检索性能: R@5=100%, QPS=75.43
8项国际标准: 100%对齐
```

---

## Phase 1: 测试止血 → v9.1-beta2

### A1: engine.py 测试套件

**目标模块**: `core/engine.py` (1,805行, 87函数, 2类, 30缺doc)

**前置条件**:
- [x] conftest.py 已存在，含 clean_engine / temp_db_path / sample_entries fixture
- [x] tests/test_core/test_engine.py 已有基础测试(5个类, ~15个测试)
- [ ] 需确认: engine.py 所有公开方法签名

**engine.py 关键类与方法清单** (从代码解析):

```
ICMEEngine:
  __init__(config, dependencies)
  remember(content, layer, tags, priority, metadata) → dict
  recall(query, layers, tags, limit) → list[MemoryEntry]
  forget(entry_id) → bool
  stats() → dict
  purge_layer(layer_name) → int
  clear_all()
  set_quality_gate(gate)
  set_llm_bridge(bridge)
  remember_batch(entries) → list    # 批量写入
  remember_async(content, layer, tags, priority) → str  # 异步写入
  fast_inject(batch_entries) → list  # 极速注入
  promote(entry_id, target_layer) → bool
  archive(entry_id) → bool
  restore(entry_id) → bool
  consolidate(from_layer) → dict
  get_entry(entry_id) → MemoryEntry|None
  search(query, layers, limit, min_score) → list
  health() → dict

MemoryEntry:
  id, content, layer, tags, priority, created_at, last_accessed
  access_count, effectiveness_score, related_ids, metadata, changelog
  size_bytes (property)
  priority_weight() → float
  value_score() → float
  update_content(new_content)
  to_dict() → dict
```

**执行指令 A1**:

```bash
# Step 1: 创建engine完整测试文件
# 文件: tests/test_core/test_engine_complete.py
```

**测试用例设计 (60个测试)**:

| 测试类 | 测试数 | 覆盖方法 |
|--------|--------|---------|
| TestMemoryEntry | 8 | size_bytes, priority_weight, value_score, update_content, to_dict |
| TestICMEEngineInit | 5 | 默认初始化, 自定义config, 依赖注入, 目录创建, SQLite初始化 |
| TestICMEEngineRemember | 8 | 基础写入, 六层写入, metadata, 批量写入, 异步写入, 极速注入, 重复内容, 空内容 |
| TestICMEEngineRecall | 7 | 基础召回, 按层过滤, 按标签过滤, limit限制, 空结果, 排序, 跨层召回 |
| TestICMEEngineForget | 4 | 正常删除, 不存在ID, 删除后recall验证, 统计更新 |
| TestICMEEngineConsolidate | 5 | 正常固结, 累积量触发, 空层固结, 固结统计, 固结事件日志 |
| TestICMEEnginePromote | 4 | 正常晋升, 不存在ID, 目标层不存在, 晋升后源层验证 |
| TestICMEEngineArchive | 4 | 正常归档, 恢复, 不存在ID, 归档统计 |
| TestICMEEngineStats | 4 | 空引擎统计, 写入后统计, 访问计数, 运行时间 |
| TestICMEEnginePurge | 3 | 清空单层, 不存在层, 清空后写入验证 |
| TestICMEEngineSearch | 4 | FTS5搜索, 标签搜索, 混合搜索, 空查询 |
| TestICMEEngineHealth | 4 | 健康检查, 容量使用率, 错误率, 运行状态 |

**中间缺失环节补全**:
1. engine.py 依赖 `processors/` 目录下的 consolidation_processor/conflict_resolver/preference_drift_detector — 需 mock 或条件跳过
2. engine.py 依赖 `learning_bridge.ClosedLoopLearningBridge` — 需 mock
3. engine.py 依赖 `sqlite_store.SQLiteMemoryStore` — 使用 temp_db_path fixture
4. `fast_inject` 和 `remember_batch` 方法需确认是否存在 — 从代码确认存在
5. `remember_async` 需要 async 测试框架 — 使用 pytest-asyncio

**验证命令**:
```bash
cd d:\元初系统\天机v9.1
python -m pytest tests/test_core/test_engine_complete.py -v --tb=short
```

---

### A2: sqlite_store.py 测试套件

**目标模块**: `core/sqlite_store.py` (844行, 30函数, 2类, 14缺doc)

**关键类与方法清单**:

```
SQLiteMemoryStore:
  __init__(db_path, cache_size, recorder, learning_engine)
  _get_conn() → sqlite3.Connection
  _init_db()                    # 建表+FTS5+索引
  store(entry_dict) → str       # 写入单条
  store_batch(entries) → list   # 批量写入
  get(entry_id) → dict|None     # 读取
  search(query, layer, tags, limit) → list  # FTS5+混合搜索
  update(entry_id, updates) → bool
  delete(entry_id) → bool
  get_by_layer(layer, limit, offset) → list
  get_stats() → StorageStats
  vacuum()                      # VACUUM优化
  health() → dict
  record_action(action, details)  # EvolutionLoop喂入
  close()

StorageStats:
  file_path, file_size_mb, total_entries, wal_size_kb,
  last_vacuum, cache_hits, cache_misses
```

**执行指令 A2**:

**测试用例设计 (40个测试)**:

| 测试类 | 测试数 | 覆盖方法 |
|--------|--------|---------|
| TestSQLiteInit | 5 | 数据库创建, WAL模式, FTS5建表, 索引创建, schema版本 |
| TestSQLiteStore | 6 | 单条写入, 批量写入, 重复ID, 空内容, 大内容, 特殊字符 |
| TestSQLiteGet | 4 | 正常读取, 不存在ID, 缓存命中, 缓存未命中 |
| TestSQLiteSearch | 6 | FTS5全文搜索, 标签搜索, 按层过滤, limit, 空结果, 中文搜索 |
| TestSQLiteUpdate | 4 | 更新内容, 更新标签, 更新优先级, 不存在ID |
| TestSQLiteDelete | 3 | 正常删除, 不存在ID, 删除后FTS5验证 |
| TestSQLiteGetByLayer | 3 | 按层获取, 分页, 空层 |
| TestSQLiteStats | 3 | 统计信息, 缓存命中率, 文件大小 |
| TestSQLiteVacuum | 2 | VACUUM执行, VACUUM后大小验证 |
| TestSQLiteHealth | 2 | 健康检查, 错误统计 |
| TestSQLiteConcurrency | 2 | 多线程写入, 多线程读取 |

**中间缺失环节补全**:
1. SQLite WAL模式在Windows上需确保文件权限 — 使用 tmp_path fixture
2. FTS5中文分词需 content_segmented 字段 — 测试需验证分词逻辑
3. EvolutionLoop 依赖需 mock — `recorder=None, learning_engine=None`
4. 线程安全: `_write_lock` + `_local` 需多线程测试

**验证命令**:
```bash
python -m pytest tests/test_core/test_sqlite_store.py -v --tb=short
```

---

### A3: quality_gate.py 测试套件

**目标模块**: `core/quality_gate.py` (936行, 49函数, 5类, 20缺doc)

**关键类与方法清单**:

```
QualityGate:
  __init__(config, engine)
  check(content, layer, tags, priority, existing_entries) → GateResult
  _check_noise(content) → dict
  _check_duplicate(content, existing_entries) → dict
  _check_will_intensity(content, priority) → dict
  _check_upstream_anchor(content, tags) → dict
  _check_conflict(content, existing_entries) → dict
  _calc_gate_effectiveness(action, state_before, state_after) → float
  _learn_from_gates(causal_pairs, effectiveness_summary) → dict
  _evolve_gate_thresholds(learn_result, mutable_config) → dict
  _get_health_metrics() → dict
  evolution_loop (property)

GateVerdict: PASS / DOWNGRADE / REJECT / CONFLICT / PENDING_UPSTREAM
GateResult: verdict, target_layer, reason, adjustments, conflicts_with, suggested_upstream, quality_dimensions
```

**执行指令 A3**:

**测试用例设计 (35个测试)**:

| 测试类 | 测试数 | 覆盖方法 |
|--------|--------|---------|
| TestGateVerdict | 4 | PASS/DOWNGRADE/REJECT/CONFLICT枚举值 |
| TestGateResult | 3 | 默认值, 自定义值, 序列化 |
| TestQualityGateInit | 3 | 默认初始化, 自定义config, engine注入 |
| TestQualityGateCheck | 8 | 正常PASS, 噪声REJECT, 重复DOWNGRADE, 冲突CONFLICT, 缺上游PENDING, 高优先级PASS, 空内容, 特殊字符 |
| TestQualityGateNoise | 3 | 短内容噪声, 纯符号噪声, 正常内容 |
| TestQualityGateDuplicate | 3 | 完全重复, 高相似度, 低相似度 |
| TestQualityGateWill | 3 | 高意志内容, 低意志内容, 意志衰减 |
| TestQualityGateEvolution | 3 | 有效性计算, 学习反馈, 阈值进化 |
| TestQualityGateHealth | 3 | 健康指标, 拒绝率, 降级率 |

**中间缺失环节补全**:
1. QualityGate 依赖 `processors/conflict_resolver` 和 `processors/preference_drift_detector` — 需 mock 或 ImportError 路径
2. `check()` 方法需要 `existing_entries` 参数 — 需构造 MemoryEntry 列表
3. `_will_tracker` 是内部状态 — 需通过多次 check() 间接测试衰减
4. EvolutionLoop 集成 — 使用 mock 验证调用

**验证命令**:
```bash
python -m pytest tests/test_core/test_quality_gate.py -v --tb=short
```

---

### A4: models.py + config.py 测试

**目标模块**:
- `core/models.py` (Pydantic模型, ~80行)
- `core/config.py` (504行, 22缺doc)

**models.py 关键类**:

```
MemoryLayer(str, Enum): sensory/working/short_term/episodic/semantic/meta
Priority(str, Enum): low/medium/high/critical
MemoryCreate(BaseModel): content, layer, tags, priority, metadata, session_id
MemoryResponse(BaseModel): id, content, layer, tags, priority, value_score, ...
MemorySearchQuery(BaseModel): query, layers, tags, priority, limit, min_score, semantic
MemoryStats(BaseModel): total_entries, total_accesses, uptime_seconds, layers, ...
AgentInfo(BaseModel): id, name, role, description
```

**config.py 关键类**:

```
MemoryLayerConfig: name, layer_index, max_size_bytes, max_entries, capacity_threshold, accumulation_threshold_bytes
QualityGateConfig: noise_threshold, min_content_length, duplicate_threshold, ...
ICMEConfig: layers, data_path, quality_gate, ...
DEFAULT_CONFIG: 全局默认配置实例
StoragePathConfig: 15个标准化存储子路径
ConfigManager: 配置管理类
SYSTEM_IDENTITY: 系统身份信息
AI_MEMORY_ROOT / MEMORY_DATA_PATH / PYTHON_EXECUTABLE
get_python_executable() → Path
```

**执行指令 A4**:

**models.py 测试 (20个测试)**:

| 测试类 | 测试数 | 覆盖 |
|--------|--------|------|
| TestMemoryLayer | 3 | 枚举值, 字符串转换, 无效值 |
| TestPriority | 3 | 枚举值, 字符串转换, 无效值 |
| TestMemoryCreate | 4 | 默认值, 必填字段, 验证, 序列化 |
| TestMemoryResponse | 4 | 字段完整性, extra=ignore, 默认值, 序列化 |
| TestMemorySearchQuery | 3 | 默认limit, 范围验证, 可选字段 |
| TestMemoryStats | 3 | 字段完整性, extra=ignore, 默认值 |

**config.py 测试 (25个测试)**:

| 测试类 | 测试数 | 覆盖 |
|--------|--------|------|
| TestMemoryLayerConfig | 4 | 创建, 默认值, 边界值, 序列化 |
| TestQualityGateConfig | 3 | 创建, 阈值范围, 序列化 |
| TestICMEConfig | 5 | 默认配置, 六层配置, 数据路径, 质量门禁, 自定义 |
| TestDefaultConfig | 3 | 实例存在, 六层完整, 路径有效 |
| TestStoragePathConfig | 4 | 15个子路径, 自动创建, 权限校验, 合规审计 |
| TestSystemIdentity | 3 | 名称/版本/端口, 一致性, 非空 |
| TestPathConstants | 3 | AI_MEMORY_ROOT, MEMORY_DATA_PATH, PYTHON_EXECUTABLE |

**中间缺失环节补全**:
1. models.py 使用 Pydantic v2 — 需确认 `model_config = {"extra": "ignore"}` 语法兼容
2. config.py 的 `DEFAULT_CONFIG` 是模块级实例 — 测试不应修改它
3. `MEMORY_DATA_PATH` 依赖环境变量 — 需 monkeypatch 测试
4. `PYTHON_EXECUTABLE` 路径在测试环境可能不存在 — 需 fallback 测试

**验证命令**:
```bash
python -m pytest tests/test_core/test_models.py tests/test_core/test_config.py -v --tb=short
```

---

### A5: CI集成 + 覆盖率门禁

**目标**: 建立自动化测试流水线 + 覆盖率门槛

**执行指令 A5**:

**Step 1: 创建 pytest 配置文件**

文件: `pyproject.toml` (追加)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
markers = [
    "unit: 单元测试",
    "integration: 集成测试",
    "slow: 慢速测试",
    "sss: SSS级关键测试",
]
addopts = "-v --tb=short -x"
```

**Step 2: 创建覆盖率配置**

文件: `.coveragerc`

```
[run]
source = core
omit =
    core/__init__.py
    core/_verify_final.py
    core/activate_l4l5.py
    core/migrate_v80_to_v81.py
    core/engine.py.bak_three_breaks

[report]
fail_under = 30
show_missing = True
exclude_lines =
    pragma: no cover
    if __name__ == .__main__
    pass
    raise NotImplementedError
```

**Step 3: 创建覆盖率门禁脚本**

文件: `scripts/coverage_gate.py`

```python
"""覆盖率门禁 — 每次提交前运行，低于阈值则失败"""
import subprocess
import sys

MIN_COVERAGE = 30  # Phase1目标30%，后续逐步提升到60%

def run_coverage():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "--cov=core",
         "--cov-report=term-missing", f"--cov-fail-under={MIN_COVERAGE}"],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"覆盖率门禁失败: 低于{MIN_COVERAGE}%")
        sys.exit(1)
    print(f"覆盖率门禁通过: ≥{MIN_COVERAGE}%")

if __name__ == "__main__":
    run_coverage()
```

**Step 4: 创建 GitHub Actions CI**

文件: `.github/workflows/test.yml`

```yaml
name: 天机v9.1 测试流水线
on: [push, pull_request]
jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt pytest pytest-cov
      - run: python -m pytest tests/ --cov=core --cov-fail-under=30 -v
```

**Step 5: 验证命令**

```bash
# 运行全量测试 + 覆盖率
python -m pytest tests/test_core/ --cov=core --cov-report=term-missing -v

# 运行覆盖率门禁
python scripts/coverage_gate.py
```

**中间缺失环节补全**:
1. `requirements.txt` 需确认是否存在 — 不存在则创建
2. `pytest-cov` 需安装 — `pip install pytest-cov`
3. `.coveragerc` 的 `fail_under=30` 是Phase1目标，后续逐步提升
4. Windows CI 需注意路径分隔符 — 使用 `pathlib.Path`
5. 当前7个测试文件可能有些已过时 — 需逐一验证可运行

**Phase1 验证清单**:

```bash
# 全量运行
python -m pytest tests/ -v --tb=short

# 覆盖率报告
python -m pytest tests/ --cov=core --cov-report=html -v

# 门禁检查
python scripts/coverage_gate.py

# 预期结果:
# - 新增测试: 60+40+35+45=180个
# - 覆盖率: 8.3% → 30%+
# - 全部PASS
```

---

## Phase 2: 灵犀探针 → v9.1-beta3

### B1: 依赖扫描器 (架构之眼)

**目标**: 自动检测模块间依赖异常/循环引用/死代码

**执行指令 B1**:

**Step 1: 创建依赖扫描器**

文件: `core/lingxi/dependency_scanner.py`

```python
"""
灵犀·架构之眼 — 依赖扫描器
功能:
  1. 扫描 core/ 目录所有 .py 文件的 import 关系
  2. 构建有向依赖图
  3. 检测循环依赖
  4. 标记死代码(未引用函数/类)
  5. 计算模块耦合度
  6. 输出 DOT 格式可视化
"""
```

**关键实现**:

| 函数 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `scan_imports(directory)` | 扫描所有import | 目录路径 | Dict[str, Set[str]] |
| `build_dependency_graph(imports)` | 构建有向图 | import映射 | networkx.DiGraph |
| `detect_cycles(graph)` | 检测循环依赖 | 有向图 | List[List[str]] |
| `find_dead_code(directory, graph)` | 标记死代码 | 目录+图 | Dict[str, Set[str]] |
| `calc_coupling(graph)` | 计算耦合度 | 有向图 | Dict[str, float] |
| `export_dot(graph, output_path)` | 导出DOT | 图+路径 | None |
| `scan_and_report(directory)` | 一键扫描+报告 | 目录路径 | Dict |

**Step 2: 创建测试**

文件: `tests/test_lingxi/test_dependency_scanner.py`

测试用例 (15个):
- 空目录扫描
- 单文件无import
- 正常import链
- 循环import检测
- 相对import解析
- 条件import处理
- 死代码检测
- 耦合度计算
- DOT导出验证
- core/目录实际扫描

**中间缺失环节补全**:
1. 需创建 `core/lingxi/` 目录和 `__init__.py`
2. 需安装 `networkx` — `pip install networkx`
3. AST解析需处理 `try/except ImportError` 模式 — 天机大量使用
4. 相对import (`.xxx`) 需解析为完整模块路径
5. `from .xxx import yyy` 需追踪到具体函数/类级别

**验证命令**:
```bash
python -c "from core.lingxi.dependency_scanner import scan_and_report; print(scan_and_report('core'))"
python -m pytest tests/test_lingxi/test_dependency_scanner.py -v
```

---

### B2: Docstring生成器 (自愈之手)

**目标**: AI辅助自动补全缺失的docstring

**执行指令 B2**:

**Step 1: 创建Docstring生成器**

文件: `core/lingxi/docstring_generator.py`

```python
"""
灵犀·自愈之手 — Docstring生成器
功能:
  1. 扫描指定模块，识别缺docstring的函数/类
  2. 解析函数签名(参数+返回值+类型注解)
  3. 调用DeepSeek LLM生成docstring
  4. 自动插入到源文件正确位置
  5. 验证插入后文件语法正确
  6. 生成变更报告
"""
```

**关键实现**:

| 函数 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `scan_missing_docstrings(file_path)` | 扫描缺doc函数 | 文件路径 | List[MissingDoc] |
| `parse_function_signature(func_node)` | 解析签名 | AST节点 | FuncSignature |
| `generate_docstring(signature, context)` | AI生成docstring | 签名+上下文 | str |
| `insert_docstring(file_path, func_name, docstring)` | 插入docstring | 文件+函数+内容 | bool |
| `verify_syntax(file_path)` | 验证语法 | 文件路径 | bool |
| `process_file(file_path, dry_run)` | 处理单文件 | 文件路径 | Dict |
| `process_directory(directory, dry_run)` | 处理目录 | 目录路径 | Dict |

**Step 2: 创建测试**

文件: `tests/test_lingxi/test_docstring_generator.py`

测试用例 (12个):
- 扫描缺doc函数
- 解析简单签名
- 解析复杂签名(类型注解+默认值)
- 生成docstring(需mock LLM)
- 插入docstring到文件
- 验证插入后语法
- dry_run模式不修改文件
- 处理整个目录
- 处理已有docstring的函数(跳过)
- 处理类方法
- 处理async函数
- 处理属性property

**中间缺失环节补全**:
1. 需依赖 `llm_bridge.py` 调用DeepSeek — 需 mock 或使用本地规则生成
2. 备选方案: 不依赖LLM，基于签名规则生成模板docstring
3. 文件修改需原子操作 — 先写临时文件，验证后rename
4. 需处理编码问题 — 天机使用UTF-8-SIG
5. 需备份原文件 — `.docstring_backup/` 目录

**验证命令**:
```bash
# dry-run模式扫描
python -c "from core.lingxi.docstring_generator import process_directory; print(process_directory('core', dry_run=True))"

# 实际执行(先备份)
python -c "from core.lingxi.docstring_generator import process_directory; print(process_directory('core', dry_run=False))"
```

---

### B3: 类型注解器

**目标**: 自动推断和补全类型注解

**执行指令 B3**:

**Step 1: 创建类型注解器**

文件: `core/lingxi/type_annotator.py`

```python
"""
灵犀·类型注解器
功能:
  1. 扫描缺类型注解的函数参数和返回值
  2. 从函数体推断类型(静态分析)
  3. 从调用点推断类型(跨函数)
  4. 生成类型注解并插入源文件
  5. 验证插入后mypy/pyright通过
"""
```

**关键实现**:

| 函数 | 功能 |
|------|------|
| `scan_missing_annotations(file_path)` | 扫描缺注解函数 |
| `infer_param_type(func_node, param_name)` | 推断参数类型 |
| `infer_return_type(func_node)` | 推断返回类型 |
| `insert_annotation(file_path, func_name, annotations)` | 插入注解 |
| `verify_with_mypy(file_path)` | mypy验证 |

**Step 2: 创建测试**

文件: `tests/test_lingxi/test_type_annotator.py`

测试用例 (10个):
- 扫描缺注解函数
- 推断字符串参数
- 推断整数参数
- 推断返回类型
- 插入注解
- 验证语法
- 处理复杂类型(Dict, List, Optional)
- 处理类方法self参数
- 处理已有部分注解
- dry_run模式

**中间缺失环节补全**:
1. 静态类型推断是NP-hard问题 — 使用启发式规则而非完全推断
2. 常见模式: `x = []` → `List`, `x = {}` → `Dict`, `x = ""` → `str`
3. 需处理 `from __future__ import annotations` — 延迟求值
4. mypy 可能未安装 — 作为可选验证步骤
5. Python 3.12 支持 `list[str]` 而非 `List[str]` — 统一使用新语法

**Phase2 验证清单**:

```bash
# B1: 依赖扫描
python -c "from core.lingxi.dependency_scanner import scan_and_report; r=scan_and_report('core'); print(f'循环依赖: {len(r[\"cycles\"])}个, 死代码: {sum(len(v) for v in r[\"dead_code\"].values())}个')"

# B2: Docstring生成(dry-run)
python -c "from core.lingxi.docstring_generator import process_directory; r=process_directory('core', dry_run=True); print(f'需补全: {r[\"missing_count\"]}个函数')"

# B3: 类型注解(dry-run)
python -c "from core.lingxi.type_annotator import process_directory; r=process_directory('core', dry_run=True); print(f'需注解: {r[\"missing_count\"]}个参数')"

# 全量测试
python -m pytest tests/test_lingxi/ -v
```

---

## Phase 3: 债务偿还 → v9.1-rc1

### C1: enforcement_hook.py 拆分

**目标**: 3,594行单体 → 5个子模块

**当前结构分析**:

```
enforcement_hook.py 包含:
  - OtelGenAISpanKind (5种SpanKind)
  - GenAIAgentAttributes (OTel属性)
  - EnforcementLevel / EnforcementHook (核心钩子)
  - EnforcementTracker / EnforcementEvolution (进化追踪)
  - EnforcementAlignment (对齐检查)
  - AdaptiveRecordingPolicy (自适应记录策略)
  - ConsumerProfile (消费者画像)
  - OWASP AOS Inspect规则库 (6类14条)
  - ISO DiAML CF映射
  - Microsoft Agent Task Span
  - OTel GenAI Evaluation 6维评分
  - ~193个函数, 60个类
```

**拆分方案**:

```
core/enforcement/
├── __init__.py              # 重新导出，保持向后兼容
├── hook_core.py             # EnforcementHook + EnforcementLevel (~600行)
├── otel_attributes.py       # OtelGenAISpanKind + GenAIAgentAttributes (~300行)
├── standards/
│   ├── __init__.py
│   ├── owasp_inspect.py     # OWASP AOS 6类14条规则 (~400行)
│   ├── iso_diaml.py         # ISO DiAML CF映射 (~350行)
│   ├── ms_agent_span.py     # Microsoft Agent Task Span (~350行)
│   └── otel_eval.py         # OTel GenAI Evaluation 6维 (~400行)
├── enforcement_evolution.py # 已存在，保持不变
├── enforcement_global_impact.py # 已存在，保持不变
├── mcp_bridge.py            # 已存在，保持不变
└── standards_compliance.py  # 已存在，保持不变
```

**执行指令 C1**:

**Step 1: 创建 standards/ 子目录**

```bash
mkdir -p core/enforcement/standards
```

**Step 2: 提取 OTel 属性到 otel_attributes.py**

从 enforcement_hook.py 中提取:
- `OtelGenAISpanKind` 枚举
- `GenAIAgentAttributes` 数据类
- `OtelGenAIToolAttributes` 数据类
- 所有 `to_otel_dict()` 方法

**Step 3: 提取 OWASP 规则到 standards/owasp_inspect.py**

从 enforcement_hook.py / standards_compliance.py 中提取:
- 6类14条 OWASP AOS 规则
- `OWASPInspector` 类
- 规则检测方法

**Step 4: 提取 ISO DiAML 到 standards/iso_diaml.py**

- `ISODiAMLMapper` 类
- CF全映射
- XML导出

**Step 5: 提取 MS Agent Span 到 standards/ms_agent_span.py**

- `MsAgentLifecycleManager` 类
- 8种SpanKind
- 任务生命周期管理

**Step 6: 提取 OTel Eval 到 standards/otel_eval.py**

- `OTelMultiDimEvaluator` 类
- 6维评分矩阵
- 加权聚合

**Step 7: 更新 __init__.py 保持向后兼容**

```python
# core/enforcement/__init__.py
from .hook_core import EnforcementHook, EnforcementLevel
from .otel_attributes import OtelGenAISpanKind, GenAIAgentAttributes
from .standards.owasp_inspect import OWASPInspector
from .standards.iso_diaml import ISODiAMLMapper
from .standards.ms_agent_span import MsAgentLifecycleManager
from .standards.otel_eval import OTelMultiDimEvaluator
# ... 所有原有导出保持不变
```

**Step 8: 更新 enforcement_hook.py 为薄代理**

```python
# core/enforcement_hook.py — 保持向后兼容
"""向后兼容入口 — 所有实现已迁移到 core/enforcement/"""
from core.enforcement import *  # noqa: F401,F403
```

**Step 9: 运行全量测试验证**

```bash
python -m pytest tests/ -v --tb=short
python -c "from core.enforcement_hook import EnforcementHook; print('兼容性OK')"
```

**中间缺失环节补全**:
1. 拆分前必须先有 engine.py + enforcement_hook 的测试 — Phase1 前置
2. `from core.enforcement_hook import XXX` 的外部引用需全部兼容 — __init__.py 重新导出
3. 拆分后每个子模块需独立测试 — 新增 tests/test_enforcement/
4. standards/ 子目录需 `__init__.py`
5. 循环import风险 — enforcement_evolution.py 被 hook_core.py 引用

---

### C2: tianji_container.py 重构

**目标**: 3,094行 → 提取容器编排逻辑

**当前结构分析**:

```
tianji_container.py 包含:
  - ModuleState 枚举
  - ModuleDescriptor / ModuleInstance 数据类
  - TianjiContainer 主类 (271函数, 34类)
  - 模块注册/启动/停止/健康检查
  - 信号路由/事件总线
  - 性能基准benchmark()
  - 容量规划
  - 递归深度控制
```

**重构方案**:

```
core/
├── tianji_container.py      # 薄代理入口 (~100行)
├── container/
│   ├── __init__.py
│   ├── core.py              # TianjiContainer 主类 (~800行)
│   ├── module_lifecycle.py  # ModuleState/Descriptor/Instance + 生命周期 (~400行)
│   ├── signal_router.py     # 信号路由 + 事件总线 (~500行)
│   ├── capacity_planner.py  # 容量规划 + 预警 (~400行)
│   └── benchmark.py         # 性能基准测试 (~300行)
```

**执行指令 C2**:

与 C1 相同的拆分流程: 提取 → 创建子模块 → 更新导出 → 薄代理 → 测试验证

---

### C3: law_domain.py 拆分

**目标**: 2,223行 → 按域拆分

**拆分方案**:

```
core/
├── law_domain.py            # 薄代理入口
├── law/
│   ├── __init__.py
│   ├── core.py              # LawDomain/LawType/LawPriority/LawLifecycle 枚举 + LawEntry 数据类
│   ├── process_laws.py      # PR-LAW 进程法则
│   ├── path_laws.py         # PATH-LAW 路径法则
│   ├── memory_laws.py       # MEM-LAW 记忆法则
│   ├── security_laws.py     # SEC-LAW 安全法则
│   ├── code_quality_laws.py # CODE-LAW 代码质量法则
│   ├── deploy_laws.py       # DEPLOY-LAW 部署法则
│   ├── agent_laws.py        # AGENT-LAW 智能体法则
│   └── engine.py            # LawDomainEngine 主引擎
```

---

### C4: 清理遗留文件

**执行指令 C4**:

```bash
# 1. 删除备份文件
del core\engine.py.bak_three_breaks

# 2. 清理 __pycache__
find . -type d -name __pycache__ -exec rm -rf {} +

# 3. 清理 .pyc
find . -name "*.pyc" -delete

# 4. 清理临时测试数据
rm -rf data/.memory/test_*
rm -rf test_*.db

# 5. 验证清理后系统正常
python -c "from core.engine import ICMEEngine; e=ICMEEngine(); print('清理后系统正常')"
python -m pytest tests/ -v --tb=short
```

**Phase3 验证清单**:

```bash
# 拆分后模块数验证
python -c "import os; files=[f for f in os.listdir('core/enforcement') if f.endswith('.py')]; print(f'enforcement模块数: {len(files)}')"

# 向后兼容验证
python -c "from core.enforcement_hook import EnforcementHook; print('enforcement_hook兼容OK')"
python -c "from core.tianji_container import TianjiContainer; print('tianji_container兼容OK')"
python -c "from core.law_domain import LawDomain; print('law_domain兼容OK')"

# 全量测试
python -m pytest tests/ -v --cov=core --cov-fail-under=40
```

---

## Phase 4: 商业化就绪 → v9.1.0

### D1: SLA保障体系

**目标**: 99.9%可用性承诺的技术支撑

**执行指令 D1**:

**Step 1: 创建健康检查框架**

文件: `core/sla/health_checker.py`

```python
"""
SLA健康检查框架
功能:
  1. 心跳检测 — 每30秒检查所有核心模块状态
  2. 深度健康检查 — 每5分钟执行完整健康评估
  3. 自动恢复 — 检测到故障自动重启/降级
  4. SLA指标计算 — 可用性/延迟/错误率
  5. 告警通知 — 超阈值触发告警
"""
```

**关键类**:

| 类 | 功能 |
|----|------|
| `HealthChecker` | 定期健康检查调度器 |
| `SLACalculator` | SLA指标计算(可用性/MTTR/MTBF) |
| `AutoRecovery` | 自动恢复策略(重启/降级/切换) |
| `AlertManager` | 告警管理(阈值/通知/升级) |

**Step 2: 创建SLA测试**

文件: `tests/test_sla/test_health_checker.py`

测试用例 (15个):
- 心跳检测正常
- 心跳检测超时
- 深度健康检查
- 可用性计算(99.9%)
- MTTR计算
- MTBF计算
- 自动恢复-重启
- 自动恢复-降级
- 告警触发
- 告警升级
- 多模块并行检查
- 历史SLA报告
- SLA趋势预测

**中间缺失环节补全**:
1. 需创建 `core/sla/` 目录
2. 心跳检测需后台线程 — 使用 `threading.Timer`
3. 自动恢复需考虑恢复次数限制 — 避免无限重启
4. SLA指标需持久化 — SQLite存储历史数据
5. 告警通知渠道 — 初始版本仅日志，后续接入邮件/webhook

---

### D2: 多租户隔离

**目标**: namespace级别的记忆隔离

**执行指令 D2**:

**Step 1: 增强现有 namespace_manager.py**

文件: `core/sla/tenant_manager.py`

```python
"""
多租户管理器
基于现有 namespace_manager.py 增强:
  1. 租户注册/注销
  2. 租户级记忆隔离(独立SQLite数据库)
  3. 租户级配额管理(条目数/存储大小/QPS)
  4. 租户级权限控制(读/写/管理)
  5. 租户使用量统计
"""
```

**关键类**:

| 类 | 功能 |
|----|------|
| `TenantManager` | 租户生命周期管理 |
| `TenantQuota` | 配额定义与检查 |
| `TenantIsolation` | 数据隔离层(路由到不同DB) |
| `TenantStats` | 使用量统计 |

**Step 2: 创建测试**

文件: `tests/test_sla/test_tenant_manager.py`

测试用例 (12个):
- 租户注册
- 租户注销
- 记忆隔离验证(租户A看不到租户B)
- 配额限制(条目数超限)
- 配额限制(存储超限)
- 权限控制(只读租户写入失败)
- 使用量统计
- 多租户并发
- 租户级配置
- 租户数据迁移
- 默认租户
- 租户删除后数据清理

**中间缺失环节补全**:
1. 现有 `namespace_manager.py` (296行) 已有基础 — 增强而非重写
2. 数据隔离策略: 每租户独立SQLite文件 vs 共享SQLite+tenant_id字段
3. 推荐方案: 共享SQLite+tenant_id字段(减少文件数) + FTS5索引含tenant_id
4. 配额检查需在 `remember()` 调用链中加入 — 修改 engine.py
5. 需向后兼容: 无租户ID时使用默认租户

---

### D3: 可观测性完善

**目标**: OTel全链路追踪

**执行指令 D3**:

**Step 1: 增强现有 tdaf_schema.py / tdaf_exporter.py**

文件: `core/sla/observability.py`

```python
"""
可观测性框架
基于现有 tdaf_schema.py / tdaf_exporter.py 增强:
  1. OTel Span 全链路追踪(remember→recall→consolidate)
  2. OTel Metrics 暴露(QPS/延迟/错误率/容量)
  3. OTel Logs 结构化日志
  4. Prometheus 指标导出
  5. Jaeger 链路追踪导出
"""
```

**关键实现**:

| 组件 | 功能 | 依赖 |
|------|------|------|
| `TianjiTracer` | Span创建/传播/导出 | opentelemetry-api |
| `TianjiMeter` | Counter/Histogram/Gauge | opentelemetry-sdk |
| `TianjiLogger` | 结构化日志 | logging + OTel |
| `PrometheusExporter` | /metrics 端点 | prometheus-client |
| `JaegerExporter` | 链路追踪导出 | opentelemetry-exporter-jaeger |

**Step 2: 创建测试**

文件: `tests/test_sla/test_observability.py`

测试用例 (10个):
- Span创建
- Span传播(跨函数)
- Metrics计数器
- Metrics直方图
- 结构化日志
- Prometheus格式导出
- Jaeger格式导出
- 全链路追踪(remember→recall)
- 性能影响测试(<5%开销)
- 降级模式(OTel不可用时)

**中间缺失环节补全**:
1. 需安装 opentelemetry 相关包 — `pip install opentelemetry-api opentelemetry-sdk`
2. Prometheus 导出需 HTTP 端点 — 与现有 8771 端口集成
3. Jaeger 导出需 Jaeger 服务 — 测试环境使用 OTLP HTTP
4. 性能开销需控制 — 采样率可配置(默认10%)
5. 降级模式: OTel不可用时退化为纯日志

---

### D4: 定价与计费模型

**目标**: 按记忆条目数+QPS+API调用计费

**执行指令 D4**:

**Step 1: 创建计费框架**

文件: `core/sla/billing.py`

```python
"""
计费框架
功能:
  1. 使用量计量(记忆条目/QPS/API调用/存储)
  2. 计费规则引擎(阶梯定价/包年/免费额度)
  3. 账单生成(日/月)
  4. 使用量预警(接近配额80%)
  5. 审计日志(所有计费操作可追溯)
"""
```

**定价模型设计**:

| 套餐 | 记忆条目 | QPS | API调用/月 | 价格 |
|------|---------|-----|-----------|------|
| 免费版 | 1,000 | 10 | 10,000 | 免费 |
| 基础版 | 50,000 | 50 | 500,000 | ¥99/月 |
| 专业版 | 500,000 | 200 | 5,000,000 | ¥499/月 |
| 企业版 | 不限 | 不限 | 不限 | 定制 |

**Step 2: 创建测试**

文件: `tests/test_sla/test_billing.py`

测试用例 (10个):
- 使用量计量
- 阶梯定价计算
- 免费额度检查
- 超额预警(80%)
- 账单生成
- 审计日志
- 多租户计费
- 套餐升级
- 套餐降级
- 退款计算

**Phase4 验证清单**:

```bash
# D1: SLA健康检查
python -c "from core.sla.health_checker import HealthChecker; hc=HealthChecker(); print(hc.check_all())"

# D2: 多租户
python -c "from core.sla.tenant_manager import TenantManager; tm=TenantManager(); print(tm.list_tenants())"

# D3: 可观测性
python -c "from core.sla.observability import TianjiTracer; print('OTel OK')"

# D4: 计费
python -c "from core.sla.billing import BillingEngine; print('Billing OK')"

# 全量测试
python -m pytest tests/ -v --cov=core --cov-fail-under=50
```

---

## 三遍迭代验证

### 第1遍: 结构完整性检查

| 检查项 | Phase1 | Phase2 | Phase3 | Phase4 |
|--------|--------|--------|--------|--------|
| 目录结构完整 | tests/test_core/ | core/lingxi/ | core/enforcement/standards/ | core/sla/ |
| __init__.py | ✅ | 需创建 | 需创建 | 需创建 |
| 测试文件 | 需创建5个 | 需创建3个 | 需创建5个 | 需创建4个 |
| 依赖声明 | requirements.txt | +networkx | 无新增 | +opentelemetry |

### 第2遍: 缺失环节补全

| 缺失环节 | 影响 | 补全方案 |
|---------|------|---------|
| requirements.txt 不存在 | CI无法安装依赖 | 创建，含pytest/pytest-cov/pytest-asyncio |
| processors/ 目录可能不存在 | engine.py ImportError | 使用 try/except + mock |
| pytest-asyncio 未安装 | 异步测试失败 | 加入 requirements.txt |
| networkx 未安装 | 依赖扫描失败 | 加入 requirements.txt |
| opentelemetry 未安装 | 可观测性失败 | 加入 requirements.txt |
| 现有7个测试可能过时 | 全量测试失败 | 逐一验证/修复/更新 |
| conftest.py 的 clean_engine fixture 依赖 config.db_path | fixture可能失效 | 更新为使用 temp_db_path |
| enforcement_hook.py 被大量模块import | 拆分后兼容性风险 | 薄代理+重新导出 |

### 第3遍: 可执行性验证

每个Phase的验证命令:

```bash
# Phase1 验证
python -m pytest tests/test_core/ -v --cov=core --cov-fail-under=30

# Phase2 验证
python -m pytest tests/test_lingxi/ -v
python -c "from core.lingxi.dependency_scanner import scan_and_report; scan_and_report('core')"

# Phase3 验证
python -m pytest tests/ -v --cov=core --cov-fail-under=40
python -c "from core.enforcement_hook import EnforcementHook; print('OK')"

# Phase4 验证
python -m pytest tests/ -v --cov=core --cov-fail-under=50
python -c "from core.sla.health_checker import HealthChecker; HealthChecker().check_all()"
```

---

## 版本里程碑

| 版本 | Phase | 覆盖率 | D级模块 | Docstring缺失 |
|------|-------|--------|---------|--------------|
| v9.1-beta1 (当前) | - | 8.3% | 43 | 53.6% |
| v9.1-beta2 | Phase1 | 30%+ | 43 | 53.6% |
| v9.1-beta3 | Phase2 | 35%+ | 43 | 35%↓ |
| v9.1-rc1 | Phase3 | 40%+ | 15↓ | 25%↓ |
| v9.1.0 | Phase4 | 50%+ | 10↓ | 20%↓ |

---

## 执行顺序与依赖关系

```
Phase1 (A1→A2→A3→A4→A5)  ← 必须最先完成，无依赖
    ↓
Phase2 (B1→B2→B3)         ← 依赖Phase1的测试基础设施
    ↓
Phase3 (C1→C2→C3→C4)     ← 依赖Phase1测试保护+Phase2的docstring生成
    ↓
Phase4 (D1→D2→D3→D4)     ← 依赖Phase3重构后的清晰架构
```

**关键约束**: Phase1必须100%完成并全部PASS后，才能启动Phase2。同理逐级递进。

---

*规划版本: v3.0 | 三遍迭代完成 | 可直接执行*
