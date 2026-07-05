# 天机v10.0.1 模块全域索引

> 本索引覆盖 `core/` 下的全部子包（22 个，其中 2 个为嵌套子包）。
> 所有条目均依据各子包 `__init__.py` 的真实导出与源文件结构生成，与代码保持一致。
> 编码: UTF-8-SIG (BOM) | 维护: @jingwei + @shiguan

---

## 子包概览

| 子包 | Phase | 文件数 | 用途 |
|---|---|---|---|
| core/shared | P0 | 10 | 共享内核Ω基点(38 Protocol/Events/Exceptions/ACL) |
| core/memory | P1 | 5 | 记忆操作(写入/晋升/归档/索引) |
| core/driver | P1 | 5 | DeepSeek驾驶者(决策/因果/紧迫/三循环编排) |
| core/storage | P1+P4 | 4+6 | 存储后端(抽象/迁移/分层 + SQLite/JSON/Tiered/Remote工厂) |
| core/orchestration | P1 | 5 | 调度编排(能力注册/追踪/管道/分发) |
| core/scheduling | P1+P2 | 8 | 智能调度(委派/定时/沙箱/批执行/优先级策略) |
| core/search | P2 | 7 | 搜索策略(FTS5/标签/语义/知识图谱/融合) |
| core/gate | P2 | 5 | 质量门禁(本地策略/政策引擎/噪声过滤) |
| core/routing | P2 | 5 | 路由策略(层级/Agent/消息) |
| core/cache | P2 | 5 | 缓存策略(内存/磁盘/远程/淘汰) |
| core/llm | P2 | 5 | LLM策略(分类/知识抽取/DeepSeek) |
| core/validation | P2 | 5 | 验证策略(序列化/条目校验/一致性) |
| core/event_wiring | P3 | 8 | 事件接线(7域Wiring + 3工厂) |
| core/memory_core | P4 | 9 | MemoryCore(6层实例+基类+每层配置) |
| core/asset_binding | P4 | 4 | L-Asset绑定(三重绑定统一服务) |
| core/container | 重构 | 3 | 依赖容器(TianjiContainer/模块生命周期) |
| core/enforcement | 重构 | 7 | 强制执行钩子(7维日志/标准合规) |
| core/enforcement/standards | 重构 | 5 | 合规标准(OWASP/ISO-DiAML/MS-Agent/OTel) |
| core/law | 重构 | 3 | 经验律令域(经验挖掘/规则生成/演化桥) |
| core/lingxi | 工具 | 4 | 灵犀探针(依赖扫描/docstring/类型标注) |
| core/sla | 商业化 | 5 | SLA支撑(健康检查/租户/可观测/计费) |
| core/storage/backends | P4 | 6 | 存储后端实现(SQLite/JSON/Tiered/Remote+工厂) |

> 说明: `core/storage` 与 `core/storage/backends`、`core/enforcement` 与
> `core/enforcement/standards` 为父子嵌套子包，单独计为 4 个独立包，
> 故子包总数为 22。"重构"指由单体大文件按职责拆分而来的子包，
> "工具/商业化"为 v9.1 起新增的工程化子包。

---

## 详细索引

### core/shared/ (Phase 0 共享内核Ω基点)

全系统零依赖的公共契约层，所有上层模块面向其接口编程，避免循环依赖。

| 文件 | 关键导出 | 说明 |
|---|---|---|
| protocols.py | 38个@runtime_checkable Protocol + GateVerdict/MemoryLayer枚举 + GateResult/SearchResult/ClusterHealth/PluginInfo | 全系统接口契约(本地/远程双实现切换点) |
| events.py | DomainEvent, EventPriority, LocalEventBus, MemoryEvents等9域事件 | 事件驱动通信基础设施 |
| exceptions.py | TianjiError, StorageError, GateError, RouteError, SearchError, PluginError | 统一异常体系 |
| types.py | EntryId, AssetId, LayerName, Metadata, Tags | 公共类型别名 |
| constants.py | ALL_LAYERS, TIANJI_VERSION, DEFAULT_PORT | 全局常量 |
| utils.py | generate_entry_id, generate_asset_id, content_hash, timestamp_ms | 通用工具函数 |
| anticorruption.py | AnticorruptionLayer, PassthroughAdapter, LoggingAdapter, DomainAdapter, CrossDomainCall | 防腐层(ACL)跨域调用 |
| plugin_interface.py | PluginInfo (插件元信息数据类) | 插件契约 |
| plugin_manager.py | 插件注册/发现管理 | 插件管理实现 |
| __init__.py | 上述异常/类型/常量/工具/ACL 统一导出 | 包入口 |

**依赖**: 无（Ω基点，仅依赖标准库）。

### core/memory/ (Phase 1 记忆操作)

由 `core/engine.py` 的庞大 ICMEEngine 按职责拆分，组件通过宿主 engine 回调协作。

| 文件 | 关键导出 | 说明 |
|---|---|---|
| __init__.py | MemoryEntry | 记忆数据模型(size_bytes/value_score/changelog) |
| writer.py | MemoryWriter | 记忆写入(remember/批量/质量门禁/资产注册) |
| promoter.py | PromotionEngine | 层级晋升(consolidate/晋升评分/自动固结) |
| archiver.py | ArchiveManager | 归档与容量(forget/驱逐/size tracking) |
| indexer.py | MemoryIndex | 检索与索引(recall/评分/tag索引) |

**依赖**: core.shared, 宿主 engine。

### core/driver/ (Phase 1 DeepSeek驾驶者)

由 `core/deepseek_driver.py` (1891+行) 按职责拆分，原模块作为路由层兼容。

| 文件 | 关键导出 | 说明 |
|---|---|---|
| decision.py | DecisionEngine, DriverDecision, EventType, TianjiEvent, EvolutionSignal, DRIVER_SYSTEM_PROMPT, EVOLUTION_EVAL_PROMPT, DEFAULT_MUTABLE_RULES | 决策引擎 |
| causal.py | CausalPair, CausalPairRecorder, CausalRecorder, OfflineCatchup | 因果对记录 |
| urgency.py | UrgencyAccumulator, EffectWatchdog | 紧迫度累积与效果看门狗 |
| orchestrator.py | DriverOrchestrator, TriggerFrequencyTracker | 三循环编排 |
| __init__.py | 上述全部 re-export | 包入口 |

**依赖**: core.shared, core.llm_bridge。

### core/storage/ (Phase 1 存储拆分)

由 `core/hybrid_engine.py` 拆分，原公开类名继续可用。

| 文件 | 关键导出 | 说明 |
|---|---|---|
| backend.py | StorageBackend | 存储后端抽象契约 |
| migration.py | MigrationManager | JSON→SQLite 迁移/增量同步 |
| tiered.py | TieredStorageEngine, MemoryTier, TierConfig, TIER_DEFAULTS | 热冷分层存储 |
| __init__.py | 上述全部 re-export | 包入口 |

**依赖**: core.shared, core.sqlite_store。

### core/storage/backends/ (Phase 4-2 存储后端策略化)

提供 4 个实现 IStorageEngine 协议的后端及统一工厂；isinstance 对全部 4 引擎为 True。

| 文件 | 关键导出 | 说明 |
|---|---|---|
| factory.py | StorageEngineFactory | 按名创建/注册/热切换/按层创建 |
| local_sqlite.py | LocalSQLiteEngine | 本地SQLite(FTS5+WAL, 委托 SQLiteMemoryStore) |
| local_json.py | LocalJSONEngine | 本地JSON(分层目录+原子写入) |
| tiered_engine.py | TieredStorageEngine | 分层混合(按layer路由到per-layer后端) |
| remote_stub.py | RemoteStorageEngine | 远程存储Stub(灵境分布式预留+降级) |
| __init__.py | 上述全部 + PLUGIN_INFO | 包入口 |

**依赖**: core.shared.protocols.IStorageEngine, core.sqlite_store。

### core/orchestration/ (Phase 1 Agent编排)

由 `core/agent_orchestrator.py` (1215行) 按职责拆分。

| 文件 | 关键导出 | 说明 |
|---|---|---|
| registry.py | CapabilityRegistry, AGENT_CAPABILITY_MATRIX, DEFAULT_REGISTRY, PipelineStage | 能力矩阵/元数据/能力查询 |
| tracker.py | ToolTracker, ToolCallTracker, AgentTask, ToolCallRecord | 工具调用追踪与统计 |
| pipeline.py | PipelineOrchestrator, AgentPipeline, StageResult | 管道编排/阶段切换/结果聚合 |
| dispatcher.py | AgentDispatcher, ParallelDispatcher | Agent选择/并行调度/分配 |
| __init__.py | 上述全部 re-export | 包入口 |

**依赖**: core.shared。

### core/scheduling/ (Phase 1+P2-5 智能调度)

由 `core/intelligent_scheduler.py` (1115行) 拆分；__init__ 集中定义跨模块共享数据结构。

| 文件 | 关键导出 | 说明 |
|---|---|---|
| __init__.py | DelegationStrategy, TaskPriority, SubAgentStatus, SubAgentTask, SubAgentResult, CronTask, DelegationDecision | 共享枚举与数据类 + re-export |
| delegation.py | DelegationDecider, DeepSeekDelegationDecider | DeepSeek驱动的委派决策 |
| cron.py | CronParser, NaturalLanguageCronEngine | 自然语言定时调度 |
| sandbox.py | ExecutionSandbox, IsolatedContextFactory | 隔离执行上下文工厂 |
| executor.py | BatchExecutor, SubAgentDelegationEngine | 并行批量子代理执行 |
| priority_strategy.py | PriorityBasedScheduler | 优先级调度策略(ISchedulerStrategy) |
| remote_stub.py | RemoteSchedulerStrategy | 灵境分布式调度 stub |
| strategy_interface.py | (调度策略接口辅助) | 策略接口层 |

**依赖**: core.shared.protocols.ISchedulerStrategy。

### core/search/ (Phase 2 搜索策略)

四通道融合检索拆分为独立 ISearchStrategy 策略插件。

| 文件 | 关键导出 | 说明 |
|---|---|---|
| fts5_strategy.py | FTS5SearchStrategy | FTS5全文检索(快) |
| tag_strategy.py | TagIndexStrategy | 标签索引精确匹配(准) |
| semantic_strategy.py | SemanticSearchStrategy | 语义向量相似度(深) |
| kg_strategy.py | KGTopologyStrategy | 知识图谱拓扑关联(全) |
| fusion_strategy.py | FusionRetrievalStrategy, ChannelPriority, ChannelResult, FusionResult, CHANNEL_WEIGHTS, RRF_K | 四通道编排 + RRF加权融合 |
| remote_stub.py | RemoteSearchStrategy | 灵境远程检索(gRPC stub) |
| __init__.py | 上述全部 re-export | 包入口 |

**依赖**: core.shared.protocols.ISearchStrategy。

### core/gate/ (Phase 2 门禁策略)

由 `core/quality_gate.py` (936行) 门禁逻辑插件化拆分。

| 文件 | 关键导出 | 说明 |
|---|---|---|
| noise_filter.py | NoiseFilter, char_ngrams, has_semantic_overlap, longest_common_substring | Q3反向过滤(冗余/矛盾/过期/噪声) |
| policy_engine.py | PolicyEngine | Q1/Q2评分 + 7因子 + 阈值管理(IGatePolicy) |
| local_gate_strategy.py | LocalGateStrategy | 三问推演本地策略(IGateStrategy) |
| remote_stub.py | RemoteGateStrategy | 灵境分布式远程策略 |
| __init__.py | 上述全部 + PLUGIN_INFO | 包入口 |

**依赖**: core.shared.protocols(GateResult/GateVerdict)。

### core/routing/ (Phase 2 路由策略)

由 `core/layer_router.py` (596行) 与 dispatcher 路由逻辑插件化为 ITaskRouter。

| 文件 | 关键导出 | 说明 |
|---|---|---|
| layer_strategy.py | LayerRoutingStrategy, LayerName, LayerTarget, PromotionGate, LAYER_PRIORITY_ORDER, LAYER_MAX_SIZE, LAYER_PROMOTION_THRESHOLD, LAYER_INDEX_FIELD, KEYWORD_PATTERNS, MULTI_TURN_THRESHOLD | 内容→记忆层级路由 |
| agent_strategy.py | AgentRoutingStrategy, DEFAULT_AGENT | 任务→Agent选择路由 |
| message_strategy.py | MessageRoutingStrategy, MESSAGE_HANDLER_MAP, DEFAULT_HANDLER | 消息→处理器路由 |
| remote_stub.py | RemoteRoutingStrategy | 灵境分布式远程策略 |
| __init__.py | 上述全部 + PLUGIN_INFO | 包入口 |

**依赖**: core.shared.protocols.ITaskRouter。

### core/cache/ (Phase 2 缓存策略)

缓存逻辑从 performance_optimizer/adaptive_retriever 提取并插件化(ICacheStrategy)。

| 文件 | 关键导出 | 说明 |
|---|---|---|
| memory_cache.py | MemoryCacheStrategy | L1进程内LRU缓存(单进程默认) |
| disk_cache.py | DiskCacheStrategy | L2磁盘JSON缓存(持久化) |
| remote_stub.py | RemoteCacheStrategy | 远程缓存(Redis/Memcached stub) |
| eviction_policy.py | LRUPolicy, TTLPolicy | 可插拔驱逐策略 |
| __init__.py | 上述全部 re-export | 包入口 |

**依赖**: core.shared.protocols.ICacheStrategy。

### core/llm/ (Phase 2 LLM策略)

由 `core/llm_bridge.py` 的 LLM 桥接逻辑插件化为 ILLMStrategy。

| 文件 | 关键导出 | 说明 |
|---|---|---|
| deepseek_strategy.py | DeepSeekLLMStrategy, PLUGIN_INFO | 本地默认策略(DeepSeek模型) |
| remote_stub.py | RemoteLLMStrategy | 远程多模型网关 stub |
| classification.py | ClassificationEngine | 内容分类能力单元 |
| knowledge_extraction.py | KnowledgeExtractionEngine | 知识提取能力单元 |
| __init__.py | 上述全部 re-export | 包入口 |

**依赖**: core.shared.protocols.ILLMStrategy。

### core/validation/ (Phase 2 序列化/验证策略)

序列化/验证逻辑从 agent_serializer/consistency_guardian 提取并插件化。

| 文件 | 关键导出 | 说明 |
|---|---|---|
| json_serializer.py | JSONSerializationStrategy | JSON序列化(datetime/dataclass/enum) |
| entry_validator.py | EntryValidationStrategy | 记忆条目字段校验(必填/类型/值范围) |
| consistency_checker.py | ConsistencyStrategy | 三重绑定一致性验证(引用/层级/版本链) |
| remote_stub.py | RemoteValidationStrategy | 远程集中式验证 stub |
| __init__.py | 上述全部 re-export | 包入口 |

**依赖**: core.shared.protocols(ISerializationStrategy/IValidationStrategy)。

### core/event_wiring/ (Phase 3 领域事件接线)

在不修改既有领域实现的前提下叠加 EventBus 发布/订阅能力(monkey-patch)，降级友好。

| 文件 | 关键导出 | 说明 |
|---|---|---|
| engine_wiring.py | EngineEventWiring, MethodWiringMixin, safe_publish, pick_arg, get_dispatch_executor | 引擎域接线(核心域,可选) |
| driver_wiring.py | DriverEventWiring | 驾驶者域接线(核心域,可选) |
| gate_wiring.py | GateEventWiring | 门禁域接线(核心域,可选) |
| orchestration_wiring.py | OrchestrationEventWiring, wire_orchestration | 编排域接线(次要域) |
| scheduling_wiring.py | SchedulingEventWiring, wire_scheduling | 调度域接线(次要域) |
| search_wiring.py | SearchEventWiring, wire_search | 搜索域接线(次要域) |
| evolution_wiring.py | EvolutionEventWiring, GovernanceEventWiring, wire_evolution_domain | 进化/治理域接线(可选) |
| __init__.py | wire_core_domains, wire_secondary_domains + 上述 re-export | 包入口与一键接线工厂 |

**依赖**: core.shared.events, core.shared.anticorruption(可选)。

### core/memory_core/ (Phase 4-1/4-3 MemoryCore六层实例化)

将 ICME 六层封装为 6 个独立 MemoryCore 运行实例，附每层独立配置体系。

| 文件 | 关键导出 | 说明 |
|---|---|---|
| base.py | MemoryCore(ABC) | 统一抽象基类(write/read/search/delete/promote/count/stats/should_consolidate) |
| config.py | CoreConfig, CoreConfigRegistry, DEFAULT_CONFIGS | 每层独立配置(override/reset/导入导出/旧版迁移) |
| core_sensory.py | SensoryCore | L0 感知层(即时捕获) |
| core_working.py | WorkingCore | L1 工作层(会话上下文) |
| core_short_term.py | ShortTermCore | L2 短期层(关键信息保持) |
| core_episodic.py | EpisodicCore | L3 情景层(决策记录/AI经验) |
| core_semantic.py | SemanticCore | L4 语义层(知识图谱/概念) |
| core_meta.py | MetaCore | L5 元层(策略自优化,顶层) |
| __init__.py | create_core, create_all_cores, PLUGIN_INFO + 上述 | 工厂与包入口 |

**依赖**: core.shared.protocols(IStorageEngine/MemoryLayer), core.config(可选)。

### core/asset_binding/ (Phase 4 L-Asset绑定层)

统一 L-Asset 三重绑定(ID映射+层级+版本链)为 AssetBindingService。

| 文件 | 关键导出 | 说明 |
|---|---|---|
| binding_protocol.py | IAssetBindingService | 绑定服务 Protocol 契约 |
| binding_service.py | AssetBindingService, PLUGIN_INFO | 本地实现(bind_memory_asset/bind_layer/bind_version_chain/verify_triple_binding/repair_binding/unbind/get_binding_stats) |
| remote_stub.py | RemoteAssetBinding | 灵境分布式 stub |
| __init__.py | 上述全部 + PLUGIN_INFO/SERVICE_PLUGIN_INFO/REMOTE_PLUGIN_INFO | 包入口 |

**依赖**: core.asset_atom, core.shared.protocols.MemoryLayer。

### core/container/ (重构: 依赖容器)

由 `core/tianji_container.py` 拆分。

| 文件 | 关键导出 | 说明 |
|---|---|---|
| core.py | TianjiContainer, build_container, get_container, set_container | 依赖注入容器 |
| module_lifecycle.py | ModuleState, ModuleDescriptor, ModuleInstance | 模块生命周期管理 |
| __init__.py | 上述全部 re-export | 包入口 |

**依赖**: core.shared。

### core/enforcement/ (重构: 强制执行钩子)

由 `core/enforcement_hook.py` 拆分的模块集合(7维日志模型+标准合规)。

| 文件 | 关键导出 | 说明 |
|---|---|---|
| hook_core.py | TianjiEnforcementHook, EnforcementDecision, SevenDimensionalLogModel, ConversationRegistry, SkillExtractionPipeline, FeedbackAwareLoop等 | 强制执行核心(7维日志/vCon/FAIR) |
| otel_attributes.py | OtelGenAISpanKind, GenAIAgentAttributes, OtelGenAISpan | OTel GenAI 属性 |
| standards_compliance.py | (标准合规聚合) | 合规聚合层 |
| mcp_bridge.py | (MCP 桥接) | enforcement↔MCP 桥接 |
| enforcement_evolution.py | (enforcement 演化) | 强制规则演化 |
| enforcement_global_impact.py | (全局影响分析) | 全局影响评估 |
| __init__.py | hook_core/otel/standards 全部 re-export | 包入口 |

**依赖**: core.shared, core.enforcement.standards。

### core/enforcement/standards/ (重构: 合规标准)

| 文件 | 关键导出 | 说明 |
|---|---|---|
| owasp_inspect.py | OWASPInspectEngine, OWASPInspectRule, OWASPInspectionColumn, OWASPAgBOMEntry, OWASPAOSObservation, OWASPAosBridge | OWASP 检查 |
| iso_diaml.py | DiAMLSerializer, ISODimension, ISOAnnotation, PROVTrace | ISO-DiAML 序列化 |
| ms_agent_span.py | MsAgentTaskSpan, MsAgentTaskSpanKind, MsAgentTaskSpanManager | MS Agent Span |
| otel_eval.py | OTelEvalEngine, OTelEvaluationBridge, OTelEvaluationSpan, EvalDimension, EvalScoringMatrix, EvalResult | OTel 评估 |
| __init__.py | 上述全部 re-export | 包入口 |

**依赖**: core.shared。

### core/law/ (重构: 经验律令域)

由 `core/law_domain.py` 拆分。

| 文件 | 关键导出 | 说明 |
|---|---|---|
| core.py | LawDomain, LawType, LawPriority, LawStatus, EmpiricalLaw, ExperiencePattern | 律令域数据模型 |
| engine.py | ExperienceMiner, LawGenerator, RuleLifecycleManager, LearningBridge, EvolutionBridge, LawDomainEngine | 经验挖掘/规则生成/演化桥 |
| __init__.py | 上述全部 re-export | 包入口 |

**依赖**: core.shared, core.learning_loop/evolution_engine(桥接)。

### core/lingxi/ (工具: 灵犀探针)

天机v9.1 代码智能分析工具集。

| 文件 | 关键导出 | 说明 |
|---|---|---|
| dependency_scanner.py | scan_imports, build_dependency_graph, detect_cycles, find_dead_code, calc_coupling, scan_and_report | 依赖扫描/循环检测/死代码 |
| docstring_generator.py | (docstring 生成) | docstring 自动生成 |
| type_annotator.py | (类型标注) | 类型注解辅助 |
| __init__.py | dependency_scanner 函数 re-export | 包入口 |

**依赖**: 标准库 ast。

### core/sla/ (商业化: SLA支撑)

商业化就绪支撑(健康/租户/可观测/计费)，子模块按可用性容错导入。

| 文件 | 关键导出 | 说明 |
|---|---|---|
| health_checker.py | HealthChecker, SLACalculator, AutoRecovery, AlertManager | 健康检查/SLA计算/自愈/告警 |
| tenant_manager.py | TenantManager, TenantQuota, TenantIsolation | 多租户管理(可选) |
| observability.py | TianjiTracer, TianjiMeter, TianjiLogger | 可观测(Trace/Meter/Log, 可选) |
| billing.py | BillingEngine, PricingTier, UsageMeter | 计费引擎(可选) |
| __init__.py | health_checker 必选 + 其余 try 导入 | 包入口 |

**依赖**: core.shared, OpenTelemetry(可选)。

---

## 依赖关系总览

```
core/shared (Ω基点, 零依赖)
   ▲
   ├── core/storage, core/storage/backends   (实现 IStorageEngine)
   ├── core/search, core/gate, core/routing   (实现各策略 Protocol)
   ├── core/cache, core/llm, core/validation  (实现各策略 Protocol)
   ├── core/scheduling                        (实现 ISchedulerStrategy)
   ├── core/memory, core/driver, core/orchestration (P1 拆分)
   ├── core/memory_core   →依赖→ IStorageEngine/MemoryLayer
   ├── core/asset_binding →依赖→ core/asset_atom + MemoryLayer
   └── core/event_wiring  →依赖→ core/shared.events (叠加于上述各域)
core/container / core/enforcement / core/law / core/lingxi / core/sla
   → 均建立在 core/shared 之上, 工程化/治理/商业化扩展
```

**核心原则**: 所有子包仅依赖 `core/shared` 的 Protocol 契约，
本地实现(LocalXxx)与远程实现(RemoteXxx stub)经工厂/容器按运行模式切换，
单进程(v9.1)与分布式(v10.0 灵境)平滑共存。
