# -*- coding: utf-8-sig -*-
"""core/__init__.py — PhaseC归位后更新导入路径

聚阵归位映射:
- memory/ (MEM): engine, hybrid_engine, sqlite_store, memory*, amim*, tcl*, asset_atom*
- processors/ (EVO): evolution*, learning_loop*, quality_gate*, auto_ops*
- enforcement/ (SEC): audit*, governance*, consistency*, resilience
- event_wiring/ (EVT): event*, conversation*, turn_logger
- orchestration/ (ORC): tvp*, task*, dag*, agent_orchestrator*, workflow_engine
- shared/ (D10): config*, models, interfaces, version, platform*, dependency_container, module_*, etc.
"""
from .memory.engine import ICMEEngine, MemoryEntry
from .shared.config import ICMEConfig, DEFAULT_CONFIG, MemoryLayerConfig, QualityGateConfig, PromotionScoreWeights
from .shared.dependency_container import DependencyContainer, TianjiContainer, ServiceLifetime, get_container, initialize_container
from .processors.quality_gate import QualityGate, GateVerdict, GateResult
from .shared.llm_bridge import LLMBridge
from .shared.models import (
    MemoryCreate, MemoryResponse, MemorySearchQuery, MemoryStats,
    ConversationSummary, AgentInfo, SummaryRequest, SummaryResponse,
    PlatformEvent, HealthStatus
)
from .shared.skill_registry import SkillRegistry, SkillSchema, SkillComposition, SkillCategory, SkillStatus
from .processors.learning_loop import ClosedLoopLearningEngine, TaskComplexity, LearningPhase, KnowledgeType
from .processors.evolution_engine import EvolutionEngine, EvolutionLevel, EvolutionStatus, RuleChange, ArchitectureProposal
from .shared.deepseek_driver import DeepSeekDriver, EventBus, TianjiEvent, EventType, CausalPairRecorder, CausalPair, EvolutionSignal, TraeConversationCapture, UrgencyAccumulator, EffectWatchdog, OfflineCatchup
from .shared.async_bridge import AsyncBridge, BridgeConfig, BridgeResult, BridgeLayer, get_bridge
from .orchestration.workflow_engine import WorkflowEngine, WorkflowDefinition, WorkflowStage, WorkflowExecution, WorkflowStatus, StageType, StageStatus
from .shared.message_gateway import MessageGateway, UnifiedMessage, PlatformType, PlatformAdapter, SessionContext
from .processors.evolution_loop import EvolutionLoop, EvolutionBus, ModuleChallenger, ModuleCausalPair, EvolutionSignal, EvolutionSignalType, EvolutionResult, LoopPhase
from .shared.module_registry import ModuleRegistry, TianjiModuleDefinition, ModuleTier, ModuleType, ModuleLifecycleState, ModuleDependency, MethodSignature, EventDef, HealthMetricDef, AuditRecord
from .shared.static_analyzer import StaticDependencyAnalyzer, StaticAnalysisReport, ValidationFinding, ValidationSeverity, ModuleLayer, analyze_and_validate, sync_analyzer_to_registry
from .enforcement.governance_pipeline import GovernancePipeline, PipelinePhase, PhaseStatus, AuditVerdict, ApprovalLevel, AuditReport, GovernanceRecord, govern_module, audit_module, create_governance_pipeline
from .processors.evolution_bus import EvolutionBus as LingjingBus, BusEvent, get_evolution_bus
from .shared.service_registry import ServiceRegistry, ServiceRecord, ServiceStatus, get_service_registry
from .enforcement.resilience import CircuitBreaker, RateLimiter, ResilienceManager, CircuitState, get_resilience_manager
from .shared.grpc_server import TianjiGRPCServer, get_grpc_server
from .shared.grpc_client import LingjingGRPCClient, GRPCClientConfig
from .shared.lingjing_manager import LingjingManager, get_lingjing_manager, GRPCServerManager, ServiceRegistryViewer, ResilienceViewer, EvolutionBusViewer, DockerManager, KnowledgeGraphViewer, AgentDispatchViewer
