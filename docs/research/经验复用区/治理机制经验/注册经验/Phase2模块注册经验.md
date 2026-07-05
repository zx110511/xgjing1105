# Phase2模块注册经验

> 来源：GovernanceOrchestrator 注册阶段开发
> 日期：2026-05-24

---

## 注册流程架构

```
GovernanceOrchestrator._run_registration_phase()
│
├─ 1. 扫描 core/ 目录所有 .py 文件（排除 __init__.py）
├─ 2. AST解析 → 提取类/函数/导入/文档字符串
├─ 3. 模块分类 → _classify_module_tier() 分配 tier + type
├─ 4. 构造 TianjiModuleDefinition
├─ 5. 调用 ModuleRegistry.register()
└─ 6. 安全检查 → 依赖项前后缀处理
```

---

## 经验：TianjiModuleDefinition 正确构造模式

### 必须字段
| 字段 | 类型 | 说明 |
|------|------|------|
| module_id | str | 模块唯一标识（文件名stem） |
| module_name | str | 模块名 |
| display_name | str | 显示名称 |
| module_version | str | 版本号 |
| tier | ModuleTier | 分层 |
| module_type | ModuleType | 类型 |
| domain | str | 所属领域 |
| responsibility | str | 职责描述（单字符串） |
| capabilities | List[str] | 能力列表 |
| anti_responsibilities | List[str] | 禁止做的事 |
| dependencies | List[ModuleDependency] | 依赖列表 |
| public_api | List[MethodSignature] | 公开API |
| events_published | List[EventDef] | 发布事件 |
| lifecycle_state | ModuleLifecycleState | 生命周期状态 |

### 禁止模式（已验证会导致错误）
- ~~`version`~~ → 不存在，用 `module_version`
- ~~`description`~~ → 不存在，用 `responsibility`
- ~~`responsibilities`~~ → 不存在（复数形式），`capabilities` 是能力列表
- ~~`events`~~ → 不存在，用 `events_published`（还有 `events_subscribed`）
- ~~`source_file`~~ → 不存在

---

## 经验：ModuleDependency 正确构造模式

```python
ModuleDependency(
    target_module="目标模块ID",      # 不是 module_id
    dependency_type=DependencyType.REQUIRED,  # 枚举，不是字符串
    description="依赖说明",
)
```

**禁止**:
- ~~`module_id=...`~~ → `target_module`
- ~~`dependency_type="internal"`~~ → `DependencyType.REQUIRED` 等枚举值
- ~~`required=True`~~ → 不存在此字段

---

## 经验：MethodSignature 正确构造模式

```python
MethodSignature(
    name="function_name",
    params=[],
    returns="Any",          # 不是 return_type
    description="说明",      # 不是 doc
)
```

---

## 经验：枚举值对照表

### ModuleTier 可用值
`CORE_ENGINE`, `BRAIN_INTELLIGENCE`, `ENFORCEMENT_COMPLIANCE`, `SCHEDULING_ORCHESTRATION`, `LEARNING_EVOLUTION`, `INFRASTRUCTURE_FOUNDATION`, `ADAPTER_INDEXING_LLM`

### ModuleType 可用值
`ENGINE`, `DRIVER`, `MANAGER`, `SCHEDULER`, `GATEWAY`, `REGISTRY`, `HOOK`, `LOOP`, `PIPELINE`, `ORCHESTRATOR`, `CAPTURE`, `QUALITY_GATE`, `ADAPTER`, `BRIDGE`, `CLIENT`

### DependencyType 可用值
`REQUIRED` ("required"), `OPTIONAL` ("optional"), `CONDITIONAL` ("conditional")

### ModuleLifecycleState 可用值
`REGISTERED`, `ACTIVE`, `DEGRADED`, `ERROR`, `DECOMMISSIONED`

---

## 模块分类策略

| 模块组 | Tier | Type | 包含模块 |
|--------|------|------|----------|
| 引擎核心 | CORE_ENGINE | ENGINE | engine, llm_bridge, hybrid_engine, config, models, router |
| 质量合规 | ENFORCEMENT_COMPLIANCE | QUALITY_GATE | quality_gate, enforcement_hook |
| 自进化 | LEARNING_EVOLUTION | LOOP | evolution_engine, evolution_loop, learning_loop, deepseek_driver |
| 调度编排 | SCHEDULING_ORCHESTRATION | SCHEDULER / ADAPTER | intelligent_scheduler, workflow_engine, message_gateway, namespace_manager |
| 基础设施 | INFRASTRUCTURE_FOUNDATION | REGISTRY | sqlite_store, chinese_tokenizer |
| 治理组件 | CORE_ENGINE | REGISTRY | module_registry, static_analyzer, governance_pipeline, tvp_bridge |

---

## 防御检查清单

- [ ] 所有枚举值已在源文件中确认存在
- [ ] 所有dataclass字段名已对照源文件验证
- [ ] dependencies 使用 ModuleDependency 对象而非字符串
- [ ] 没有重复的关键字参数
- [ ] 没有使用不存在的字段名
> 🔄 自动更新于 2026-05-24 09:51:13（源文件变更触发）