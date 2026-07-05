# 天机v10.0.1 API参考

> 本参考列出 `core/` 各域核心公开 API，签名均与源码一致。
> 约定: `MemoryLayer` 为 `core.shared.protocols.MemoryLayer` 枚举；
> `entry`/返回 `dict` 为记忆条目字典。编码 UTF-8-SIG。

---

## 1. MemoryCore API

来源: `core/memory_core/__init__.py`, `core/memory_core/base.py`

### create_all_cores(storage_engine=None, configs=None) → dict[str, MemoryCore]
创建全部 6 层 MemoryCore 实例，返回 `{层级名称: MemoryCore}`。
`storage_engine` 为 None 时各层使用进程内 dict 模拟；`configs` 为 `{层级名称: 配置覆盖}`。

### create_core(layer, storage_engine=None, config=None) → MemoryCore
创建指定层级实例。`layer` 接受 `str` 或 `MemoryLayer`；非法层级抛 `ValueError`。

### MemoryCore.write(entry: dict) → str
写入条目，返回 `entry_id`（抽象方法，各层差异化实现）。

### MemoryCore.read(entry_id: str) → dict | None
读取条目；不存在返回 None（抽象方法）。

### MemoryCore.search(query: str, *, limit: int = 20) → list[dict]
检索本层条目（抽象方法）。

### MemoryCore.delete(entry_id: str) → bool
软删除条目（通用实现）。

### MemoryCore.promote() → int
检查并执行晋升到下一层，返回晋升条目数（抽象方法）。

### MemoryCore.count() → int
当前有效条目数。

### MemoryCore.stats() → dict
层统计：`{layer, layer_index, priority, count, max_entries, usage_ratio, capacity_threshold, operations, backend}`。

### MemoryCore.should_consolidate() → bool
占用率 ≥ `capacity_threshold` 时返回 True。

**只读属性**: `layer → MemoryLayer`、`layer_name → str`、`config → dict`。

**六层实现类**: `SensoryCore` / `WorkingCore` / `ShortTermCore` / `EpisodicCore` / `SemanticCore` / `MetaCore`。

---

## 2. Storage API

来源: `core/storage/backends/__init__.py`, `core/storage/backends/factory.py`, `core/shared/protocols.py`

### StorageEngineFactory.create(name: str, **kwargs) → IStorageEngine
按名称创建后端实例（`name ∈ {"sqlite","json","tiered","remote"}`）。

### StorageEngineFactory.available_backends() → list[str]
返回已注册后端名称列表。

### StorageEngineFactory.register(name: str, engine_cls: type) → None
注册自定义后端（类方法）。

### StorageEngineFactory.create_for_layer(...) → IStorageEngine
按记忆层级创建对应后端实例（类方法）。

### IStorageEngine.insert(entry: dict) → str
写入记忆条目，返回 `entry_id`。

### IStorageEngine.get(entry_id: str) → dict | None
读取记忆条目；不存在返回 None。

### IStorageEngine.search(query: str, *, limit: int = 20, **kwargs) → list[dict]
检索记忆（`kwargs` 支持 layer/tags 等过滤）。

### IStorageEngine.delete(entry_id: str) → bool
软删除记忆。

### IStorageEngine.stats() → dict
存储统计（总量/各层分布/容量占用等）。

**后端实现**: `LocalSQLiteEngine` / `LocalJSONEngine` / `TieredStorageEngine` / `RemoteStorageEngine`（均满足 `@runtime_checkable` 的 `IStorageEngine`）。

---

## 3. Config API

来源: `core/memory_core/config.py`

### CoreConfigRegistry.create_default() → CoreConfigRegistry
基于 `DEFAULT_CONFIGS` 深拷贝装配含默认 6 层配置的注册表（类方法）。

### CoreConfigRegistry.from_icme_config(icme_config) → CoreConfigRegistry
从旧版 `ICMEConfig` 批量迁移创建（类方法，经 `CoreConfig.from_legacy`）。

### CoreConfigRegistry.get(layer: MemoryLayer) → CoreConfig
获取单层配置；未注册抛 `KeyError`。

### CoreConfigRegistry.register(layer: MemoryLayer, config: CoreConfig) → None
注册单层配置；`config.layer` 须与 `layer` 一致且通过校验，否则抛 `ValueError`。

### CoreConfigRegistry.override(layer, key, value) → None
运行时覆盖单字段，覆盖后立即校验，非法则自动回滚并抛 `ValueError`。

### CoreConfigRegistry.reset(layer) → None
重置某层到注册基线；无基线抛 `KeyError`。

### CoreConfigRegistry.has(layer) → bool / all_configs() → dict
查询某层是否注册 / 获取全部层配置浅拷贝。

### CoreConfigRegistry.export_config_tree() → dict
导出 `{"version", "layer_count", "layers": {层值: 配置字典}}`（分布式同步预留）。

### CoreConfigRegistry.import_config_tree(tree: dict) → None
覆盖式导入配置树，每层经 `validate` 后注册并刷新基线。

**CoreConfig**: `to_dict()/from_dict()`、`from_legacy()`、`validate() → (bool, str)`；
派生属性 `max_size_mb`/`accumulation_threshold_mb`/`hard_cap_mb`。

---

## 4. AssetBinding API

来源: `core/asset_binding/binding_service.py`, `core/asset_binding/binding_protocol.py`

### AssetBindingService.bind_memory_asset(memory_id: str, entry: dict) → AssetAtom
绑定1：建立 `memory_id ↔ asset_id` 映射，返回新建的 `AssetAtom`。

### AssetBindingService.bind_layer(asset_id: str, target_layer: str) → bool
绑定2：校验并设置 `asset.layer = memory.layer` 同层约束。

### AssetBindingService.bind_version_chain(asset_id: str, parent_id: str) → bool
绑定3：建立 `version + parent_version_id` 版本链 DAG。

### AssetBindingService.verify_triple_binding(asset_id: str) → dict
校验三重绑定一致性，返回校验报告字典。

### AssetBindingService.repair_binding(asset_id: str) → int
修复不一致的绑定，返回修复项数量。

### AssetBindingService.unbind(asset_id: str) → bool
解除资产绑定。

### AssetBindingService.get_binding_stats() → dict
返回绑定统计信息。

> 构造: `AssetBindingService(registry=None, snapshot_manager=None)`；
> `registry` 为 None 时启用内存模式，可独立测试。
> 协议: 实现 `IAssetBindingService`；远程实现 `RemoteAssetBinding`(stub)。

---

## 5. Event API

来源: `core/shared/events.py`, `core/event_wiring/__init__.py`

### LocalEventBus.publish(event, payload=None) → None
发布事件。兼容三种形式：`publish(DomainEvent)`(推荐) / `publish(event_type, payload)`(协议双参) / `publish(任意对象)`(自动包装)。

### LocalEventBus.publish_async(event, payload=None) → None (async)
异步发布事件。

### LocalEventBus.subscribe(event_type: str, handler) → None
订阅事件；`subscribe("*", handler)` 接收所有事件。

### LocalEventBus.unsubscribe(event_type: str, handler) → None
取消订阅。

### wire_core_domains(engine=None, driver=None, gate=None, event_bus=None, acl=None) → dict
一键接线核心域(engine/driver/gate)；组件为 None 或核心域未就绪时跳过，`event_bus` 为 None 时透传。

### wire_secondary_domains(orchestrator=None, scheduler=None, retriever=None, event_bus=None, acl=None) → dict
一键接线次要域(orchestration/scheduling/search)，返回成功接线的域。

### wire_evolution_domain(...) → ...
进化/治理域接线（`EvolutionEventWiring`/`GovernanceEventWiring`，按可用性导入）。

> 事件载体: `DomainEvent(event_type, source="", payload={}, priority=EventPriority.NORMAL, timestamp, event_id)`；
> 优先级枚举 `EventPriority`(LOW/NORMAL/HIGH/CRITICAL)；
> 9 域预定义事件常量类 `MemoryEvents` / `GateEvents` 等。

---

## 6. 策略接口 API (Protocol 契约)

来源: `core/shared/protocols.py`（38 个 `@runtime_checkable` Protocol）

| 域 | 接口 | 核心方法 |
|---|---|---|
| 存储 | IStorageEngine / ILayerStorage / IBatchStorage / IStorageMigrator | insert/get/search/delete/stats; store/retrieve/count/clear; batch_*; migrate/rollback/verify |
| 搜索 | ISearchStrategy / IFusionRetriever / IReranker / IQueryExpander | search/get_capabilities; retrieve/set_weights; rerank; expand |
| 事件 | IEventBus / IEventHandler / IEventFilter | publish/subscribe/unsubscribe; handle/can_handle; should_process |
| 门禁 | IGateStrategy / IQualityGate / IGatePolicy | check/get_verdict; evaluate/get_config; should_apply/get_threshold |
| 晋升 | IConsolidationStrategy / IPromotionGate / IConsolidationScheduler | select_candidates/promote; can_promote/score; schedule/get_next_window |
| 图谱 | IGraphEngine / IGraphQuery / ITripleExtractor | add_node/add_edge/query/sync_from_memories; query_neighbors/shortest_path/subgraph; extract/batch_extract |
| 资产 | IAssetRegistry / IAssetBinding / IAssetSnapshot | register/get/list/verify_binding; bind/unbind/get_binding; create_snapshot/restore/diff |
| 主动记忆 | IActiveMemory / IInterceptLayer / IIntentExtractor | intercept_input/intercept_response; capture_user_input/capture_ai_response; extract_intent/classify |
| 插件 | IPlugin / IPluginManager | activate/deactivate/get_info; load/unload/list/get |
| 调度 | IAgentDispatcher / ITaskRouter / ISchedulerStrategy | dispatch/get_available_agents; route/get_routing_strategy; decide/schedule/evaluate_capacity |
| LLM | ILLMStrategy | classify/extract_knowledge/generate_summary/expand_query |
| 缓存 | ICacheStrategy | get/put/delete/clear/stats |
| 适配器 | IAdapterStrategy | get_platform_info/on_event/remember/recall |
| 验证 | ISerializationStrategy / IValidationStrategy | serialize/deserialize; validate_entry/validate_integrity |
| 防腐层 | IDomainAdapter / IAnticorruptionLayer | adapt_request/adapt_response/get_supported_methods; register_adapter/call/call_async |

**枚举/数据类**: `GateVerdict`(PASS/DOWNGRADE/REJECT/CONFLICT/PENDING_UPSTREAM)、
`MemoryLayer`(sensory/working/short_term/episodic/semantic/meta)、
`GateResult` / `SearchResult` / `ClusterHealth` / `PluginInfo`。

---

## 7. 兼容层 API (v9.1)

为保证 v9.1 单进程代码无感升级，拆分前的原模块保留为路由/兼容层，原 import 路径继续可用：

| 兼容入口 (原路径) | 实际拆分子包 | 说明 |
|---|---|---|
| `core.hybrid_engine` (TieredStorageEngine/MemoryTier/TierConfig/ICMEStorageEngine) | core.storage | 存储引擎拆分 |
| `core.deepseek_driver` (DeepSeekDriver 等) | core.driver | 驾驶者拆分 |
| `core.intelligent_scheduler` (DelegationDecider 等) | core.scheduling | 智能调度拆分 |
| `core.agent_orchestrator` (CapabilityRegistry 等) | core.orchestration | Agent编排拆分 |
| `core.quality_gate` (QualityGate/GateVerdict/GateResult) | core.gate | 门禁拆分 |
| `core.layer_router` (LayerRoutingStrategy 等) | core.routing | 路由拆分 |
| `core.engine` (ICMEEngine/MemoryEntry) | core.memory | 记忆操作拆分 |
| `core.tianji_container` (TianjiContainer 等) | core.container | 依赖容器拆分 |
| `core.enforcement_hook` / `core.law_domain` | core.enforcement / core.law | 强制执行/律令域拆分 |

> 兼容原则: 拆分仅按职责重组实现，对外公开类名/符号保持不变，
> 旧版 `from core.xxx import ...` 全部继续可用，v9.1 运行不受影响。
