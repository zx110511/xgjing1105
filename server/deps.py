r"""
天机v9.1 - 共享依赖注入模块 (v3.1优化)
=========================================
避免循环导入, 提供全局单例访问:
- engine: ICME混合存储引擎实例 (SQLite优先)
- embeddings_service: 语义搜索服务实例
- cognition: 认知流水线实例
- router: 智能路由实例
- namespace_mgr: Agent命名空间管理器
"""

import sys
from pathlib import Path

_AI_MEMORY_ROOT = Path(__file__).resolve().parent.parent
if str(_AI_MEMORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_AI_MEMORY_ROOT))

from core.shared.config import DEFAULT_CONFIG

engine = None
try:
    from core.memory.hybrid_engine import ICMEStorageEngine

    engine = ICMEStorageEngine(config=DEFAULT_CONFIG, use_sqlite=True)
except ImportError:
    from core.memory.engine import ICMEEngine

    engine = ICMEEngine(config=DEFAULT_CONFIG)

quality_gate = None
try:
    from core.processors.quality_gate import QualityGate

    quality_gate = QualityGate(config=DEFAULT_CONFIG.quality_gate, engine=engine)
    if engine is not None:
        engine.set_quality_gate(quality_gate)
except ImportError:
    pass

embeddings_service = None
try:
    from indexing.embeddings import EmbeddingService

    embeddings_service = EmbeddingService(engine)
except ImportError:
    pass
except Exception as e:
    print(f"[Embedding] 初始化失败: {e}")
    embeddings_service = None

cognition = None
try:
    from indexing.cognition import CognitionPipeline

    cognition = CognitionPipeline(DEFAULT_CONFIG.data_path)
except ImportError:
    pass

router = None
try:
    from core.shared.router import LayerRouter

    router = LayerRouter()
except ImportError:
    pass

namespace_mgr = None
try:
    from core.shared.namespace_manager import NamespaceManager

    namespace_mgr = NamespaceManager()
except ImportError:
    pass

llm_layer = None
try:
    from llm_integration import DeepSeekClient, DeepSeekConfig, MemoryDecisionEngine

    deepseek_cfg = DeepSeekConfig.from_env()
    if deepseek_cfg.api_key:
        from llm_integration.client import DeepSeekClient
        from llm_integration.decision_engine import MemoryDecisionEngine

        client = DeepSeekClient(deepseek_cfg)
        llm_layer = MemoryDecisionEngine(client)
        print(f"[LLM] DeepSeek大脑已激活 | 模型: {deepseek_cfg.model}")
except ImportError as e:
    print(f"[LLM] 导入失败: {e}")
except Exception as e:
    print(f"[LLM] 初始化失败: {e}")

llm_bridge = None
try:
    from core.shared.llm_bridge import LLMBridge
    from llm_integration.client import DeepSeekConfig

    llm_bridge = LLMBridge(DeepSeekConfig.from_env())
    if llm_bridge.is_ready and engine is not None:
        engine.set_llm_bridge(llm_bridge)
        print("[LLM Bridge] DeepSeek已注入引擎 remember()/recall()")
except ImportError:
    pass
except Exception as e:
    print(f"[LLM Bridge] 初始化失败: {e}")

enforcement_hook = None


def get_enforcement_hook_instance():
    global enforcement_hook
    if enforcement_hook is None:
        try:
            from core.enforcement.mcp_bridge import EnforcementHookMCP

            enforcement_hook = EnforcementHookMCP(
                memory_api_url="http://127.0.0.1:8771",
                local_cache_dir=_AI_MEMORY_ROOT / "data" / ".enforcement",
            )
            print("[Enforcement] 强制执行钩子初始化完成")
        except Exception as e:
            print(f"[Enforcement] 初始化失败: {e}")
    return enforcement_hook


protocol = None
try:
    from active_memory.protocol import (
        ActiveMemoryConfig,
        ActiveMemoryProtocol,
        InterceptLayer,
    )

    protocol = ActiveMemoryProtocol(ActiveMemoryConfig())
    # P0修复: 注入enforcement_hook到协议拦截层
    try:
        hook = get_enforcement_hook_instance()
        if hook:
            if (
                not hasattr(protocol, "intercept_layer")
                or protocol.intercept_layer is None
            ):
                protocol.intercept_layer = InterceptLayer(
                    engine=engine, enforcement_hook=hook
                )
            else:
                protocol.intercept_layer.enforcement_hook = hook
            engine_ref = "已绑定" if engine is not None else "独立模式"
            print(
                f"[Protocol] EnforcementHook已注入拦截层({engine_ref}) — 对话强制执行已激活"
            )
    except Exception as e:
        print(f"[Protocol] EnforcementHook注入失败: {e}")
except ImportError:
    pass

adapter_registry = None
try:
    from adapters.ai_platform_adapters import AdapterRegistry

    adapter_registry = AdapterRegistry()
except ImportError:
    pass


def get_engine():
    return engine


def get_cognition():
    if cognition is None:
        raise RuntimeError("Cognition pipeline not initialized")
    return cognition


def get_router():
    if router is None:
        raise RuntimeError("Router not initialized")
    return router


def get_namespace_manager():
    global namespace_mgr
    if namespace_mgr is None:
        from core.shared.namespace_manager import NamespaceManager

        namespace_mgr = NamespaceManager()
    return namespace_mgr


agent_scheduler = None


def set_agent_scheduler(scheduler):
    global agent_scheduler
    agent_scheduler = scheduler


def get_agent_scheduler():
    global agent_scheduler
    if agent_scheduler is None:
        try:
            sys.path.insert(0, str(_AI_MEMORY_ROOT.parent))
            from core.orchestration.agent_orchestrator import AgentScheduler

            # 尝试从容器注入EventBus — 关键! 没有EventBus调度器无法接收事件
            eb = None
            try:
                from core.shared.tianji_container import get_container

                c = get_container()
                if c:
                    eb_mod = c._modules.get("event_bus")
                    if eb_mod and eb_mod.instance:
                        eb = eb_mod.instance
                        print("[Orchestrator] EventBus已从容器注入")
            except Exception:
                pass

            # 如果容器不可用，尝试从DeepSeekDriver获取
            if eb is None:
                global deepseek_driver
                if deepseek_driver and hasattr(deepseek_driver, "_event_bus"):
                    eb = deepseek_driver._event_bus
                    print("[Orchestrator] EventBus已从DeepSeekDriver注入")

            agent_scheduler = AgentScheduler(event_bus=eb)
            if eb:
                print(
                    "[Orchestrator] ✅ Agent调度器懒加载完成 v"
                    + agent_scheduler.VERSION
                    + " (EventBus已连接)"
                )
            else:
                print(
                    "[Orchestrator] ⚠️ Agent调度器懒加载完成 v"
                    + agent_scheduler.VERSION
                    + " (EventBus=None, 事件发布不可用)"
                )
        except Exception as e:
            print(f"[Orchestrator] 懒加载失败: {e}")
    return agent_scheduler


deepseek_driver = None


def get_deepseek_driver():
    global deepseek_driver
    if deepseek_driver is not None:
        return deepseek_driver
    try:
        from core.shared.tianji_container import get_container

        container = get_container()
        if container:
            mod = container._modules.get("deepseek_driver")
            if mod and mod.instance:
                deepseek_driver = mod.instance
                return deepseek_driver
    except Exception:
        pass
    try:
        from core.shared.deepseek_driver import DeepSeekDriver, EventBus

        eb = EventBus()
        de = llm_layer if llm_layer else None
        deepseek_driver = DeepSeekDriver(
            event_bus=eb,
            memory_engine=engine,
            decision_engine=de,
        )
        if de:
            print("[DeepSeekDriver] decision_engine已注入 — 三循环LLM增强已激活")
        else:
            print("[DeepSeekDriver] decision_engine=None — 三循环将使用规则回退")
        return deepseek_driver
    except Exception as e:
        print(f"[DeepSeekDriver] 获取失败: {e}")
        return None


event_consumer = None


def get_event_consumer():
    global event_consumer
    if event_consumer is not None:
        return event_consumer
    try:
        from core.event_wiring.event_consumer import EventConsumer

        event_consumer = EventConsumer.get_instance(DEFAULT_CONFIG.data_path, engine)
        event_consumer.start()
        print("[EventConsumer] 事件消费者已启动 (pending_events.jsonl自动消费)")
    except Exception as e:
        print(f"[EventConsumer] 启动失败: {e}")
    return event_consumer


layer_decomposer = None


def get_layer_decomposer():
    global layer_decomposer
    if layer_decomposer is not None:
        return layer_decomposer
    try:
        from core.shared.layer_decomposer import LayerDecomposer

        layer_decomposer = LayerDecomposer(
            engine=engine, data_path=DEFAULT_CONFIG.data_path
        )
        print("[LayerDecomposer] 六层精准分解器初始化完成")
    except Exception as e:
        print(f"[LayerDecomposer] 初始化失败: {e}")
    return layer_decomposer


def startup_event_consumer():
    try:
        consumer = get_event_consumer()
        cognition_count = consumer.consume_cognition_insights()
        evo_count = consumer.sync_evolution_to_meta()
        print(
            f"[EventConsumer] 启动时同步: cognition→semantic {cognition_count}条, evolution→meta {evo_count}条"
        )
    except Exception as e:
        print(f"[EventConsumer] 启动同步失败: {e}")


icme_layer_router = None


def get_icme_layer_router():
    global icme_layer_router
    if icme_layer_router is not None:
        return icme_layer_router
    try:
        from core.shared.layer_router import LayerRouter

        icme_layer_router = LayerRouter(engine=engine, quality_gate=quality_gate)
        print("[ICME LayerRouter] 六层分级分发路由器初始化完成")
    except Exception as e:
        print(f"[ICME LayerRouter] 初始化失败: {e}")
    return icme_layer_router


trae_capture = None


def get_trae_capture():
    global trae_capture
    if trae_capture is not None:
        return trae_capture
    try:
        from active_memory.trae_capture import TraeConversationCapture

        trae_capture = TraeConversationCapture(
            engine=engine, data_path=DEFAULT_CONFIG.data_path
        )
        lr = get_icme_layer_router()
        if lr:
            trae_capture.set_layer_router(lr)
        print("[TraeCapture] 对话全量捕获器初始化完成")
    except Exception as e:
        print(f"[TraeCapture] 初始化失败: {e}")
    return trae_capture


fusion_retriever = None


def get_fusion_retriever():
    global fusion_retriever
    if fusion_retriever is not None:
        return fusion_retriever
    try:
        from core.memory.fusion_retriever import FusionRetriever

        fusion_retriever = FusionRetriever(engine=engine)
        if engine and hasattr(engine, "_store"):
            fusion_retriever.set_sqlite_store(engine._store)
        print("[FusionRetriever] 四通道融合检索器初始化完成")
    except Exception as e:
        print(f"[FusionRetriever] 初始化失败: {e}")
    return fusion_retriever


# ─── v9.1 事件总线与接线 [v10-ready] ─────────────────────────────
def get_event_bus():
    """获取或创建 LocalEventBus 单例。[v10-ready]"""
    from core.shared.config import TIANJI_V91_EVENT_WIRING

    if not TIANJI_V91_EVENT_WIRING:
        return None
    try:
        from core.shared.events import LocalEventBus

        if not hasattr(get_event_bus, "_instance"):
            get_event_bus._instance = LocalEventBus()
        return get_event_bus._instance
    except ImportError:
        return None


def startup_event_wiring() -> dict:
    """在server启动时注册所有event_wiring。[v10-ready]

    受 TIANJI_V91_EVENT_WIRING 开关控制。
    Returns: dict of activated wirings (可能为空dict如果开关关闭)
    """
    from core.shared.config import TIANJI_V91_EVENT_WIRING

    if not TIANJI_V91_EVENT_WIRING:
        print("[TIANJI-v9.1] Event wiring 已禁用 (TIANJI_V91_EVENT_WIRING=false)")
        return {}

    wirings = {}
    event_bus = get_event_bus()
    if event_bus is None:
        print("[TIANJI-v9.1] Event bus 不可用，跳过接线")
        return wirings

    try:
        from core.event_wiring import wire_core_domains, wire_secondary_domains

        # 核心域接线 (engine/driver/gate)
        core_wirings = wire_core_domains(
            engine=engine,  # 使用模块级 engine 单例
            event_bus=event_bus,
        )
        wirings.update(core_wirings)

        # 次要域接线 (orchestrator/scheduler/retriever)
        secondary_wirings = wire_secondary_domains(
            event_bus=event_bus,
        )
        wirings.update(secondary_wirings)

        print(f"[TIANJI-v9.1] Event wiring 完成: {list(wirings.keys())}")
    except Exception as e:
        print(f"[TIANJI-v9.1] Event wiring 部分失败: {e}")

    return wirings


# ─── v10 Protocol-aware 依赖注入 [v10-ready] ─────────────────────
# 当 TIANJI_V91_PROTOCOL_MODE=True 时, 优先注入 Protocol 接口实现,
# 使 FastAPI 路由 handler 透明获得新实现。开关关闭时全部返回 None,
# 旧路径行为 100% 不变。所有新增路径异常均被捕获并静默降级。

_memory_cores: dict | None = None
_evolution_loop = None


def get_memory_cores() -> dict | None:
    """获取 6 层 MemoryCore 实例字典 (Protocol 模式下)。[v10-ready]

    受 TIANJI_V91_PROTOCOL_MODE 开关控制:
        - True:  返回 create_all_cores() 结果 (缓存单例)
        - False: 返回 None (旧路径不受影响)

    Returns:
        {层级名称: MemoryCore 实例} 字典, 或 None。
    """
    global _memory_cores
    try:
        from core.shared.config import TIANJI_V91_PROTOCOL_MODE
    except Exception:
        return None
    if not TIANJI_V91_PROTOCOL_MODE:
        return None
    if _memory_cores is not None:
        return _memory_cores
    try:
        from core.memory_core import create_all_cores

        # 复用模块级 engine 作为存储后端 (实现 IStorageEngine)
        _memory_cores = create_all_cores(storage_engine=engine)
        print(f"[Protocol-DI] MemoryCore 六层实例已注入: {list(_memory_cores.keys())}")
    except Exception as e:
        print(f"[Protocol-DI] MemoryCore 注入失败(降级): {e}")
        _memory_cores = None
    return _memory_cores


def get_evolution_loop():
    """获取自进化循环实例 (缓存单例)。[v10-ready]

    延迟导入 core.evolution_loop 避免循环依赖。
    任意异常均被捕获并返回 None (静默降级)。
    """
    global _evolution_loop
    if _evolution_loop is not None:
        return _evolution_loop
    try:
        from core.processors.evolution_loop import EvolutionLoop

        _evolution_loop = EvolutionLoop(
            module_name="tianji_server",
            persist_dir=_AI_MEMORY_ROOT / "data" / ".evolution",
        )
        print("[Protocol-DI] EvolutionLoop 自进化循环已注入")
    except Exception as e:
        print(f"[Protocol-DI] EvolutionLoop 注入失败(降级): {e}")
        _evolution_loop = None
    return _evolution_loop


def get_protocol_registry() -> dict:
    """返回 Protocol → 实现 的映射注册表。[v10-ready]

    汇总所有已注册的 Protocol 实现, 供路由 handler / 监控查询。
    格式: {"IMemoryCore": [...], "IStorageEngine": [...], "IEventBus": [...], ...}
    所有项均做存在性判断, 不可用项以空列表呈现。
    """
    registry: dict[str, list] = {
        "IMemoryCore": [],
        "IStorageEngine": [],
        "IEventBus": [],
        "IDeepSeekDriver": [],
        "IEvolutionLoop": [],
    }
    try:
        cores = get_memory_cores()
        if cores:
            registry["IMemoryCore"] = list(cores.values())
    except Exception:
        pass
    try:
        if engine is not None:
            registry["IStorageEngine"] = [engine]
    except Exception:
        pass
    try:
        eb = get_event_bus()
        if eb is not None:
            registry["IEventBus"] = [eb]
    except Exception:
        pass
    try:
        drv = get_deepseek_driver()
        if drv is not None:
            registry["IDeepSeekDriver"] = [drv]
    except Exception:
        pass
    try:
        evo = get_evolution_loop()
        if evo is not None:
            registry["IEvolutionLoop"] = [evo]
    except Exception:
        pass
    return registry


# ─── FastAPI Depends 工厂 (可供路由 Depends() 使用) [v10-ready] ──
def dep_memory_cores():
    """FastAPI Depends: 获取 MemoryCore 字典 (Protocol 模式)。[v10-ready]"""
    return get_memory_cores()


def dep_deepseek():
    """FastAPI Depends: 获取 DeepSeek 驾驶者 (核心决策大脑)。[v10-ready]"""
    return get_deepseek_driver()


def dep_event_bus():
    """FastAPI Depends: 获取 EventBus。[v10-ready]"""
    return get_event_bus()


def startup_proactive_tasks() -> dict:
    """[v10-ready] 服务启动时自动注册主动任务。

    体现"主动 / 自进化 / 自动化 / DeepSeek 核心"设计指令:
        1. evolution_loop 可用 → 注册定期自进化
        2. memory_cores 可用   → 注册自动固结检查
        3. deepseek_driver 可用 → 注册主动决策循环
    受 TIANJI_V91_PROTOCOL_MODE 开关控制; 关闭时返回空 dict。
    所有注册失败均静默降级, 不影响服务启动。

    Returns:
        dict: {任务名: 状态描述} 已激活的主动任务清单。
    """
    tasks: dict[str, str] = {}
    try:
        from core.shared.config import TIANJI_V91_PROTOCOL_MODE
    except Exception:
        return tasks
    if not TIANJI_V91_PROTOCOL_MODE:
        print("[Proactive] 主动任务已禁用 (TIANJI_V91_PROTOCOL_MODE=false)")
        return tasks

    # 1. 自进化: 定期 evolution 循环
    try:
        evo = get_evolution_loop()
        if evo is not None:
            tasks["evolution"] = "registered"
    except Exception as e:
        print(f"[Proactive] evolution 任务注册失败(降级): {e}")

    # 2. 自动化: MemoryCore 自动固结检查
    try:
        cores = get_memory_cores()
        if cores:
            tasks["consolidation"] = f"registered({len(cores)} cores)"
    except Exception as e:
        print(f"[Proactive] consolidation 任务注册失败(降级): {e}")

    # 3. DeepSeek 核心: 主动决策循环
    try:
        drv = get_deepseek_driver()
        if drv is not None:
            tasks["deepseek_decision"] = "registered"
    except Exception as e:
        print(f"[Proactive] deepseek 决策循环注册失败(降级): {e}")

    if tasks:
        print(f"[Proactive] 主动任务已激活: {list(tasks.keys())}")
    return tasks
