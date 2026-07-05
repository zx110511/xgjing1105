# Phase2集成审计Bug案例集

> 来源：天机v9.1 GovernanceOrchestrator 集成到 tianji_launcher.py 全过程
> 审计日期：2026-05-24
> 审计等级：SSS级
> 最终结果：72/72 = 100%通过

---

## Bug#1: 重复的 `anti_responsibilities` 关键字参数

**发现位置**: `tests/test_phase2_real_audit.py`
**错误信息**: `TianjiModuleDefinition.__init__() got multiple values for keyword argument 'anti_responsibilities'`
**根因**: 模块定义创建时重复指定了 `anti_responsibilities` 参数
**修复**: 删除重复行
**教训**: 构造dataclass对象时检查参数唯一性

---

## Bug#2: `report.dependencies` 未赋值

**发现位置**: `core/static_analyzer.py`
**错误信息**: 报告依赖字段为空
**根因**: 静态分析报告未填充 `dependencies` 字段
**修复**: 添加 `report.dependencies = all_imports` 显式赋值
**教训**: 关键输出字段必须有显式赋值，不可依赖隐式初始化

---

## Bug#3: `target_module` 前缀未剥离

**发现位置**: `core/static_analyzer.py` → `sync_analyzer_to_registry`
**错误信息**: 内部导入的 `.` 前缀与模块ID不兼容
**根因**: 相对导入 ".module_name" 直接作为模块ID使用
**修复**: 添加 `target_module.lstrip(".")` 剥离前缀
**教训**: 导入路径与模块ID之间需要规范化映射

---

## Bug#4: 状态管理使用字符串而非枚举

**发现位置**: `core/governance_pipeline.py`
**错误信息**: 模块状态为 "active" 字符串
**根因**: 使用了字符串 "active" 而非 `ModuleLifecycleState.ACTIVE`
**修复**: 更新为使用枚举值
**教训**: 状态管理强制使用枚举类型，禁止魔法字符串

---

## Bug#5: `ModuleTier.SELF_EVOLUTION` 不存在

**发现位置**: `tianji_launcher.py` → `_classify_module_tier()`
**错误信息**: `AttributeError: type object 'ModuleTier' has no attribute 'SELF_EVOLUTION'`
**根因**: 假设枚举值存在但未验证实际定义
**实际值**: `LEARNING_EVOLUTION`
**修复**: 替换为 `ModuleTier.LEARNING_EVOLUTION`
**教训**: **使用枚举值前必须确认实际枚举定义，不可凭经验假设**

---

## Bug#6: `ModuleTier.DATA_PERSISTENCE` 不存在

**发现位置**: `tianji_launcher.py` → `_classify_module_tier()`
**错误信息**: `AttributeError: type object 'ModuleTier' has no attribute 'DATA_PERSISTENCE'`
**根因**: 同Bug#5，假设了不存在的枚举值
**实际值**: `INFRASTRUCTURE_FOUNDATION`
**修复**: 替换为 `ModuleTier.INFRASTRUCTURE_FOUNDATION`
**教训**: 批量枚举引用需逐一对照源文件验证

---

## Bug#7: `ModuleType` 多个值不存在

**发现位置**: `tianji_launcher.py` → `_classify_module_tier()`
**涉及错误值**:
- `ModuleType.EVOLUTION_LOOP` → 应为 `ModuleType.LOOP`
- `ModuleType.STORAGE` → 应为 `ModuleType.REGISTRY`
- `ModuleType.SERVICE` → 应为 `ModuleType.ORCHESTRATOR`
**根因**: 同Bug#5/#6
**修复**: 逐一替换为实际枚举值
**教训**: `ModuleType` 枚举共15个值：ENGINE, DRIVER, MANAGER, SCHEDULER, GATEWAY, REGISTRY, HOOK, LOOP, PIPELINE, ORCHESTRATOR, CAPTURE, QUALITY_GATE, ADAPTER, BRIDGE, CLIENT

---

## Bug#8~#12: dataclass字段名批量不匹配（"影子字段"模式）

**发现位置**: `tianji_launcher.py` → `_run_registration_phase()`

| Bug# | 类 | 错误字段 | 正确字段 | 影响 |
|------|-----|---------|---------|------|
| #8 | MethodSignature | `return_type`, `is_async`, `is_public`, `doc` | `returns`, `description` | API方法签名无效 |
| #9 | EventDef | `payload_schema` | 不存在，直接移除 | 事件定义无效 |
| #10 | HealthMetricDef | `name`, `threshold_warning`, `threshold_critical`, `description` | `metric_name`, `warn_threshold`, `critical_threshold` | 健康指标无效 |
| #11 | TianjiModuleDefinition | `version`, `description`, `responsibilities`, `events`, `source_file` | `module_version`, `responsibility`, `events_published` | 模块定义无效 |
| #12 | ModuleDependency | `module_id`, `dependency_type="internal"`, `required` | `target_module`, `dependency_type=DependencyType.REQUIRED` | 依赖关系无效 |

**根因模式**: 生成代码时假设dataclass字段名，未对照源文件验证。这类Bug具有高度重复性。
**修复**: 逐一对照 `core/module_registry.py` 中的dataclass定义修正字段名
**核心教训**: **任何dataclass的构造调用必须与实际定义对照验证，这是SSS审计的"开户行检查"**

---

## 经验总结

### 防御措施
1. **枚举值预验证**: 使用枚举前必须 `print(list(EnumClass))` 确认可用值
2. **dataclass字段对照**: 构造dataclass对象前必须对照源文件确认字段签名
3. **私有方法勿假设**: 不使用未经验证的私有方法（如 `_create_import_visitor`），优先使用公共API
4. **SSS审计自动化**: 审计脚本应自动检测dataclass字段匹配

### 异常模式
- **"影子字段"陷阱**: 凭经验命名字段 → 与真实定义不符 → 注册/分析等流程静默失败
- **枚举假设陷阱**: 枚举值按英文语义猜测 → 实际枚举值使用不同命名规范

> 上述异常模式已标记，建议入天机L3 Episodic层供未来查询。