# Plan: 优化天机v9.1智能体智能调度系统（自定义+Trae内置）v4.2

## Summary

本计划旨在解决当前天机v9.1智能调度系统中的三个核心不一致问题，并在最新"科学+智能"调度技术资源驱动下进行架构升级：

1. **命名体系未同步**：`.trae/agents/AGENT-NAMING-V3.md` 仍为v4.0旧版，未纳入7个Trae官方Agent和2个Trae内置Agent的中文命名规范。
2. **能力矩阵数据源分裂**：运行时代码 `core/orchestration/registry.py` 的 `AGENT_CAPABILITY_MATRIX` 与 `_AGENT_REGISTRY.json` 不同步，缺少 tianji/wanxiang 等Agent，且未包含Trae官方Agent和内置Agent。
3. **调度系统未覆盖全部Agent**：MCP `agent_framework.py` 的 `AGENT_CAPABILITIES` 仅23个天机Agent，`AgentRoutingStrategy` 无法识别31个自定义Agent+2个内置Agent，导致调度路由不完整。

本计划将统一命名规范、统一能力矩阵、扩展调度引擎，并引入**MCP Workflow Engine智能-执行分离**、**SKYAPI结构感知阶段编排**、**Uno-Orchestra选择性委派**、**AdaptOrch任务自适应拓扑**、**CLEAR科学评估框架**等最新研究成果，使Trae面板层31个自定义Agent和2个内置Agent全部纳入天枢智能调度体系，并实现科学可量化的调度优化。

---

## Current State Analysis

### 已确认的资产

| 资产 | 路径 | 当前状态 |
|------|------|---------|
| 智能体注册表（31个） | `.trae/agents/_AGENT_REGISTRY.json` | 已更新为31个Agent（24天机+7官方），11维联动完整 |
| 天机系列配置文件 | `.trae/agents/tianji-{id}.json` | 24个文件完整，中文名统一 |
| Trae官方配置文件 | `.trae/agents/trae-official-{ui-designer,...}.json` | 7个文件已本地化，中文名已配置 |
| 命名规范文档 | `.trae/agents/AGENT-NAMING-V3.md` | v4.0内容但文件名含V3，未包含官方/内置Agent命名 |
| 运行能力矩阵 | `core/orchestration/registry.py` | 约20个天机Agent，缺少tianji/wanxiang/官方Agent/内置Agent，emoji/名称与注册表不一致 |
| MCP调度能力 | `mcp/server/agent_framework.py` | `AGENT_CAPABILITIES`仅23个天机Agent，调度无法识别官方Agent |
| 路由策略 | `core/routing/agent_strategy.py` | 依赖 `AGENT_CAPABILITY_MATRIX`，扩展性受限 |
| 调度编排器 | `core/orchestration/agent_orchestrator.py` | 架构完善，但未加载全部31+2个Agent元数据 |
| A2A网关 | `core/orchestration/a2a_gateway.py` | 具备AgentCard能力，未暴露官方/内置Agent卡片 |

### 关键问题

1. **数据源不一致**：`_AGENT_REGISTRY.json` 是配置权威源，但运行时 `AGENT_CAPABILITY_MATRIX` 是硬编码副本，两者已出现漂移。
2. **官方Agent未进入运行时**：7个Trae官方Agent仅存在于JSON配置文件，调度器、MCP agent_dispatch、路由策略均不认识它们。
3. **内置Agent无定义**：Trae内置的 `Chat` 和 `Agent` 在天机体系中没有身份定义，无法参与TVP调度和记忆闭环。
4. **命名文档滞后**：`AGENT-NAMING-V3.md` 文件名与内容版本不匹配，且未覆盖官方/内置Agent。
5. **调度策略缺少科学优化**：当前路由主要基于关键词匹配，缺少结构感知、成本感知、拓扑自适应、反馈学习等科学机制。

---

## Part I: 科学基础 —— 最新智能体调度技术资源

本节汇总并吸收2025-2026年智能体调度与编排领域的关键论文、框架与协议，作为天机v9.1调度系统升级的"科学底座"。

### 1.1 MCP Workflow Engine：智能与执行的解耦

**来源**：Parmar, A. S. (2026). *Separating Intelligence from Execution: A Workflow Engine for the Model Context Protocol*. arXiv:2605.00827.

**核心论断**：
> 在主流架构中，Agent必须在每个会话中为每一次工具调用进行推理，token消耗与执行动作数量成正比——即使该任务以前已经解决过。MCP Workflow Engine通过将"智能（决定做什么）"与"执行（实际执行）"解耦，解决了这一根本低效问题。

**关键机制**：
- **两阶段生命周期**：
  - **Phase 1 - 设计（Design）**：一次性、高智能密集型阶段。Agent探索可用工具、学习schema、组合计划。
  - **Phase 2 - 执行（Execution）**：重复性、机械阶段。工具调用参数解析、结果在步骤间传递、错误重试。
- **Workflow Blueprint**：Agent在设计阶段输出一个声明式JSON工件，指定有向的MCP工具调用序列、参数化模板、循环、并行分支和数据管道。
- **MCP Mediator模式**：一个MCP server同时作为下游MCP servers的client，实现统一编排层。
- **执行收益**：在生产级Kubernetes CMDB同步任务（67个编排步骤、2个MCP server、38个namespace、13个worker node、22种资源类型）中，实现：
  - 每次执行token成本降低 **>99%**
  - 完整集群图（1200+节点、2800+关系）在 **45秒内** 完成
  - 确定性、幂等执行，运行时零Agent参与

**对天机的启示**：
- 将高频、重复性的MCP工具调用序列（如记忆检索、健康检查、格式化导出）沉淀为可复用的workflow blueprint。
- 天机调度器应区分"智能决策路径"和"执行流水线"，避免每次调度都重新推理完整工具链。
- 引入 `run_workflow` 工具调用原语，使一次LLM调用即可触发复杂MCP工作流。

### 1.2 SKYAPI：结构感知的多智能体API编排

**来源**：Wang, P. (2025). *SKYAPI: Structural-Aware Orchestration for LLM-Based Multi-Agent Systems*. University of Illinois Urbana-Champaign.

**核心论断**：
> 现有API路由策略通常孤立地优化每个请求，未能考虑多智能体协作中的结构依赖和同步障碍。SKYAPI将优化范式从"每次查询选择"转变为"阶段级编排"。

**关键机制**：
- **动态阶段分解与预测（Dynamic Stage Decomposition and Prediction）**：
  - 将工作流划分为有序执行阶段：
    - **链式阶段（Chain-style）**：串行依赖
    - **Map-Reduce式阶段（Map-Reduce-style）**：并行执行
  - 采用双预测机制：结构分析识别阶段边界 + 轻量模型估计输出token长度。
- **混合整数线性规划（MILP）**：显式优化阶段makespan与货币成本之间的权衡。
- **前缀感知调度与TTFT延迟**：通过Time-To-First-Token（TTFT）延迟最大化协作Agent之间的KV-cache复用。

**实验收益**：在DeepResearch和Gama-Bench等复杂基准上，SKYAPI在满足严格延迟约束的前提下，将运营成本降低最多 **3倍**。

**对天机的启示**：
- 天机调度器应在任务分解后生成**任务依赖图（DAG）**，并基于DAG结构选择链式或Map-Reduce执行阶段。
- 对跨Agent的LLM调用进行阶段级批处理与KV-cache感知调度，降低token成本与延迟。
- 将MILP优化器作为可选模块集成到 `agent_orchestrator.py`，用于高价值/高频任务的调度优化。

### 1.3 Uno-Orchestra：基于强化学习的动态选择性委派

**来源**：Cui, Z. et al. (2026). *Uno-Orchestra: Parsimonious Agent Routing via Selective Delegation*. arXiv:2605.05007.

**核心论断**：
> 传统LLM多智能体系统依赖刚性编排：要么采用扁平的每次查询路由，要么采用人工设计的任务分解。分解深度、worker选择和推理预算无法在单一目标下联合优化。Uno-Orchestra通过选择性分解任务并将每个子任务分派给合适的（模型，原语）组合，实现了统一的目标优化。

**关键机制**：
- **模型-原语（Model, Primitive）对**：一个primitive是封闭词汇表中的原子可路由动作，由worker模型执行，形成可接受对 `p = (m, s)`。
- **联合决策**：一个因果语言模型同时输出任务分解计划和每个子任务的（模型，原语）路由决策。
- **两阶段训练**：
  - 监督微调（SFT）：基于61,201条教师蒸馏轨迹。
  - 强化学习（RL）：使用AGENTIC-GRPO算法在困难任务池上优化长期奖励，奖励函数同时考虑正确性和归一化轨迹成本。
- **选择性委派**：学习何时任务分解有帮助、何时分解会增加不必要的开销和延迟。

**实验收益**：在13个基准（数学、代码、知识、长上下文、工具使用）上：
- 达到 **77.0% macro pass@1**
- 比最强workflow基线高出约 **16个百分点**
- 每次查询成本降低约 **10倍**

**对天机的启示**：
- 天机调度策略应从"固定规则路由"进化为"学习型路由"，根据任务历史反馈优化分解与委派策略。
- 将每个Agent视为（模型，原语）对，建立Agent能力-成本映射表，作为路由决策依据。
- 在天机L3 Episodic/L4 Semantic中积累调度轨迹，为未来的RL优化提供训练数据。

### 1.4 AdaptOrch：任务自适应拓扑选择

**来源**：Yu, G. (2026). *AdaptOrch: Task-Adaptive Multi-Agent Orchestration in the Era of LLM Performance Convergence*. arXiv:2602.16873.

**核心论断**：
> 当不同提供商的LLM在基准性能上趋于一致时，单一模型选择的边际收益递减，而编排拓扑（多个Agent如何协调、并行和综合）成为主导系统级性能的关键因素。

**关键机制**：
- **性能收敛缩放定律（Performance Convergence Scaling Law）**：在模型能力ε-收敛条件下，编排拓扑导致的系统性能方差超过模型选择方差的 `Ω(1/ε²)` 倍。
- **四种经典拓扑**：
  - 并行（Parallel）
  - 串行（Sequential）
  - 层级（Hierarchical）
  - 混合（Hybrid）
- **拓扑路由算法（Topology Routing Algorithm）**：基于任务分解DAG在 `O(|V|+|E|)` 时间内映射到最优编排模式。
- **自适应综合协议（Adaptive Synthesis Protocol）**：具有可证明终止保证和启发式一致性评分。

**实验收益**：在SWE-bench、GPQA和RAG任务上，拓扑感知编排比静态单拓扑基线提升 **12–23%**，即使使用相同底层模型。

**对天机的启示**：
- 天机现有的6种协作模式（A-串行、B-并行、C-层级、D-工业化、E-事件驱动、F-进化闭环）应增加**自动拓扑选择层**。
- 根据任务DAG的形状属性（并行宽度、关键路径深度、子任务耦合度）动态选择最优协作模式。
- 在 `agent_orchestrator.py` 中增加 `TopologyClassifier` 模块，将任务DAG映射到天机协作模式。

### 1.5 CLEAR框架：企业级Agent系统的科学评估

**来源**：Mehta, S. (2025). *Beyond Accuracy: A Multi-Dimensional Framework for Evaluating Enterprise Agentic AI Systems*. arXiv:2511.14136.

**核心论断**：
> 现有Agent基准主要评估任务完成准确率，忽视了成本效率、可靠性和运营稳定性等企业级关键需求。CLEAR框架从五个维度评估Agent系统：Cost（成本）、Latency（延迟）、Efficacy（效能）、Assurance（安全性）、Reliability（可靠性）。

**关键发现**：
- 仅优化准确率会导致Agent比成本感知替代方案昂贵 **4.4–10.8倍**。
- 领先Agent在类似准确率水平下成本变化高达 **50倍**（$0.10–$5.00/任务）。
- Agent性能从单次运行的60%下降到8次运行一致性的25%，可靠性评估缺失。
- CLEAR比纯准确率评估更能预测生产成功率（相关系数ρ=0.83 vs ρ=0.41）。

**关键指标**：
- **SLA Compliance Rate (SCR)**：`SCR = 在SLA内完成的任务数 / 总任务数 × 100%`
- **成本归一化**：考虑每次查询的token消耗、API调用次数、模型选择成本。
- **可靠性**：多次运行一致性、故障恢复时间、错误传播范围。

**对天机的启示**：
- 天机调度系统的优化目标应从"成功率单一指标"升级为"CLEAR五维综合指标"。
- 在 `quality_metrics` 中增加CLEAR指标采集：调度成本、端到端延迟、SLA合规率、可靠性得分、安全/合规得分。
- 使用CLEAR框架评估本次调度系统升级的效果，确保满足"综合评分达到9.9以上"的项目硬性约束。

### 1.6 Microsoft Agent Framework：MCP驱动的编排模式

**来源**：Microsoft Developer Community Blog (2025). *Orchestrating Multi-Agent Intelligence: MCP-Driven Patterns in Agent Framework*.

**核心机制**：
- **四种多智能体模式**：Single Agent、Handoff、Reflection、Magentic Orchestration。
- **模块化运行时设计**：通过 `.env` 配置切换不同编排模式，无需修改后端、前端或记忆层。
- **MCP连接一切**：Agent、工具、记忆通过共享context接口连接，支持Cosmos DB持久化会话状态。
- **模式动态切换**：
  ```python
  agent_module_path = os.getenv("AGENT_MODULE")
  agent_module = __import__(agent_module_path, fromlist=["Agent"])
  Agent = getattr(agent_module, "Agent")
  ```

**对天机的启示**：
- 天机调度系统应支持通过配置或TVP协议动态切换协作模式，无需修改核心代码。
- 将MCP作为Agent、工具、记忆的统一context层，强化现有 `mcp_bridge.py` 的桥接能力。
- 引入Reflection模式作为进化闭环（模式F）的实现形式之一。

### 1.7 Temporal + MCP：Ambient Agent的耐久编排

**来源**：Temporal Blog (2025). *Orchestrating ambient agents with Temporal*.

**核心机制**：
- **Ambient Agent**：24×7持续运行的主动Agent，不需要用户显式触发。
- **Temporal原语作为MCP工具**：将Workflows、Signals、Queries作为Agent调用的工具。
- **Schedules**：定期触发"nudge" workflow，使Agent周期性主动执行任务。
- **Signals & Queries**：Agent间通信语言，支持状态查询和事件信号。
- **耐久执行**：进程重启后schedule仍然有效，确保长期运行的Agent工作流可靠。

**对天机的启示**：
- 天机v9.1已在后台持续运行，可进一步引入Temporal-like耐久调度层，确保长期Agent任务不丢失。
- 将 `@qianli`（监控）、`@zhuiguang`（性能）、`@huasheng`（进化）等需要周期性执行的Agent迁移到耐久schedule模式。
- 在 `evt`（事件聚阵）中增强schedule/signal/query原语。

### 1.8 A2A协议：跨Agent互操作标准

**来源**：Google A2A Protocol (2025), now Linux Foundation; Habler et al. (2025). *Building A Secure Agentic AI Application Leveraging Google's A2A Protocol*. arXiv:2504.16902.

**核心机制**：
- **Agent Card**：Agent能力广告，通常托管在 `/.well-known/agent-card.json`。
- **Task生命周期**：`submitted → working → input-required → completed/failed/canceled`。
- **传输层**：HTTP + SSE + JSON-RPC 2.0。
- **与MCP互补**：A2A处理Agent间协调，MCP处理Agent与工具/数据的访问。

**安全考量（MAESTRO威胁建模）**：
- Agent Card管理风险：篡改、伪造。
- 任务执行完整性：防止任务篡改和未授权特权提升。
- 认证机制：OAuth、API keys、mTLS。

**对天机的启示**：
- 天机A2A网关应暴露全部33个Agent（31自定义+2内置）的Agent Card，包含source字段（tianji/trae-official/trae-builtin）。
- 为A2A任务生命周期添加安全校验，包括身份认证、任务完整性、输入审查。
- 将A2A作为天机与外部Agent生态互操作的官方接口。

### 1.9 其他关键资源

- **Jyothi et al. (2025)**. *MCP Server for Multi-Agent AI Assistants with Persistent Memory*. Engineering Research. 强调持久记忆、上下文管理、工作流编排对多Agent系统的必要性，提出任务分解、调度、监控的编排引擎。
- **Mohammadi et al. (2025)**. *Evaluation and Benchmarking of LLM Agents: A Survey*. KDD '25. 系统梳理Agent评估目标（行为、能力、可靠性、安全性）与评估过程，强调企业级可靠性保证和合规需求。
- **TrustOrch (2025)**. *Dynamic Trust-Aware Orchestration Framework*. 提出动态信任评估、对抗鲁棒性、自适应协作拓扑，对天机安全聚阵（SEC）的调度安全加固有参考价值。
- **CardinalHQ (2025)**. *Why MCP Beats Integrations*. 阐述MCP将"工作流为中心"的集成转变为"上下文为中心"的契约，将执行顺序决策推迟到运行时，对天机context-first设计有指导意义。

---

## Part II: 优化后的架构设计

### 2.1 总体目标

在天机v9.1现有6大协作模式（A-串行、B-并行、C-层级、D-工业化、E-事件驱动、F-进化闭环）基础上，新增三层"科学智能"调度能力：

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: 智能优化层 (Intelligence Optimization Layer)       │
│  - Uno-Orchestra选择性委派 (学习型路由)                       │
│  - AdaptOrch拓扑自动选择                                      │
│  - SKYAPI结构感知阶段编排                                     │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: 编排执行层 (Orchestration Execution Layer)         │
│  - MCP Workflow Engine (智能-执行分离)                        │
│  - 六种协作模式 (A-F)                                         │
│  - Temporal耐久调度                                           │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Agent资源层 (Agent Resource Layer)                 │
│  - 33个Agent (24天机+7官方+2内置)                             │
│  - _AGENT_REGISTRY.json 统一注册表                            │
│  - A2A Agent Card 暴露                                        │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 新增核心组件

#### 2.2.1 WorkflowBlueprintManager（工作流蓝图管理器）

**职责**：
- 沉淀高频MCP工具调用序列（如记忆检索、健康检查、格式导出、审计流程）。
- 将LLM一次性设计的工作流蓝图存储到L4 Semantic层。
- 运行时通过 `run_workflow` 触发蓝图执行，避免重复推理。

**关键接口**：
```python
class WorkflowBlueprintManager:
    def design(self, task: TaskSpec) -> Blueprint: ...
    def store(self, blueprint: Blueprint) -> str: ...
    def execute(self, blueprint_id: str, params: dict) -> ExecutionResult: ...
    def list_blueprints(self, tags: list[str]) -> list[BlueprintMeta]: ...
```

#### 2.2.2 TopologyClassifier（拓扑分类器）

**职责**：
- 根据任务分解DAG的形状属性选择最优协作模式。
- 将DAG属性映射到天机6种协作模式。

**分类规则**：
| DAG特征 | 推荐模式 | 说明 |
|---------|---------|------|
| 全部节点独立 | B-并行分析 | 无依赖，可并行执行 |
| 线性链 | A-串行流水线 | 严格顺序依赖 |
| 扇出+聚合 | C-层级分解 | 主控协调子任务 |
| 多里程碑+交付 | D-工业化生产 | S0-S6完整流程 |
| 异步事件驱动 | E-事件驱动 | 发布-订阅模式 |
| 反馈迭代 | F-进化闭环 | 检测→分析→改进→验证 |

#### 2.2.3 StageScheduler（阶段调度器）

**职责**：
- 将任务DAG划分为链式阶段和Map-Reduce阶段。
- 对每个阶段进行MILP优化（成本 vs 延迟）。
- 管理阶段间的同步屏障和数据管道。

#### 2.2.4 LearningRouter（学习路由器）

**职责**：
- 收集历史调度轨迹（任务、Agent选择、成本、延迟、成功率）。
- 基于历史数据优化Agent选择策略。
- 为Uno-Orchestra式RL训练准备数据。

### 2.3 CLEAR评估指标集成

在 `_AGENT_REGISTRY.json` 的 `quality_metrics` 中统一增加CLEAR指标：

| 维度 | 指标 | 采集方式 |
|------|------|---------|
| **Cost** | 每次调度token消耗、API调用次数、模型成本 | `mcp_bridge.py` 拦截器 |
| **Latency** | 端到端任务完成时间、TTFT、阶段延迟 | `StageScheduler` 计时器 |
| **Efficacy** | 任务完成率、质量评分、用户满意度 | `tiewei` Stage Gate |
| **Assurance** | 安全漏洞数、合规通过率、权限检查 | `zhenshan` 安全扫描 |
| **Reliability** | 多次运行一致性、故障恢复率、SLA合规率 | `qianli` 监控统计 |

---

## Part III: 具体实施变更

### Change 1: 同步更新命名规范文档

**文件**：`.trae/agents/AGENT-NAMING-V3.md`

**What**：
- 将文档标题从 `v4.0 科学化重建版` 更新为 `v4.2 扩展版（含Trae官方与内置Agent）`。
- 新增两个表格：
  - **Trae官方系列Agent命名**（7个）：UI设计师、前端架构师、后端架构师、API测试专家、AI集成工程师、性能优化专家、合规检查专家。
  - **Trae内置智能体命名**（2个）：对话（Chat）、智能体（Agent）。
- 在"命名规范"节补充官方/内置Agent的ID规则：
  - Trae官方：`{english-id}`（如 `ui-designer`），程序调用 `@ui-designer`，文档引用 `UI设计师(@ui-designer)`。
  - Trae内置：`trae-chat`、`trae-agent`，界面显示保留原Trae名称，天机内部以 `builtin:` 前缀区分。
- 在"文件命名标准"节补充：`Trae官方Agent定义文件: .trae/agents/trae-official-{english-id}.json`。

**Why**：命名规范是智能体矩阵的基础法则，必须在配置、代码、文档三处一致。

**How**：
1. 读取当前 `_AGENT_REGISTRY.json` 提取31个Agent的准确中文名/英文名/层级。
2. 在 `AGENT-NAMING-V3.md` 末尾新增"扩展命名表"章节。
3. 更新文件头部的版本号和生效日期。

---

### Change 2: 运行时能力矩阵与注册表统一

**文件**：`core/orchestration/registry.py`

**What**：
- 将 `AGENT_CAPABILITY_MATRIX` 重构为从 `.trae/agents/_AGENT_REGISTRY.json` 加载，而非硬编码。
- 加载时合并两个来源：
  - `_AGENT_REGISTRY.json` 中的31个自定义Agent（含11维联动数据）。
  - 内置Agent定义：`trae-chat`（对话）、`trae-agent`（智能体），标记 `source: "trae-builtin"`。
- 提供向后兼容字段：`name`, `layer`, `role`, `emoji`, `capabilities`, `tools`，供 `dispatcher.py`、`agent_strategy.py`、`tracker.py` 直接使用。
- 保留 `CapabilityRegistry` 类，增强其方法：
  - `load_from_registry(path)`：从 `_AGENT_REGISTRY.json` 加载。
  - `get_builtin_agents()`：返回内置Agent元数据。
  - `find_by_source(source)`：按来源过滤Agent。
  - `find_by_capability(capability)`：扩展支持官方Agent。
  - `get_clear_metrics(agent_id)`：返回Agent的CLEAR质量指标。

**Why**：消除硬编码与配置之间的漂移，确保运行时调度器与配置文件完全一致。

**How**：
1. 实现 `RegistryLoader` 内部类，解析 `_AGENT_REGISTRY.json` 的 `agents` 和 `_meta`。
2. 将 `AGENT_CAPABILITY_MATRIX` 初始化为 `CapabilityRegistry().matrix` 的延迟加载结果，或直接加载。
3. 处理加载失败时的降级：若 `_AGENT_REGISTRY.json` 不存在或解析失败，回退到当前硬编码矩阵（并记录警告）。

---

### Change 3: MCP调度框架识别全部Agent

**文件**：`mcp/server/agent_framework.py`

**What**：
- 将 `AGENT_CAPABILITIES` 硬编码字典替换为从 `_AGENT_REGISTRY.json` 动态加载。
- `_handle_agent_dispatch` 支持识别31个自定义Agent + 2个内置Agent。
- 扩展 `INTENT_PATTERNS`，增加官方Agent相关意图：
  - UI设计、前端开发、后端开发、API测试、AI集成、性能优化、合规审查。
- `_scan_agents` 除了扫描 `.qoder/agents` 和 `.trae/agents` 的 `.md`/`.json` 文件外，还解析 `trae-official-*.json` 提取其 `capabilities` 和 `inter_agent_calling.when_to_call` 用于匹配。
- `system_status` 返回的Agent统计从按目录文件数改为按 `_AGENT_REGISTRY.json` 实际注册数（31个自定义 + 2个内置）。
- 新增 `_load_workflow_blueprints()`：从L4 Semantic或本地目录加载MCP Workflow Blueprints。

**Why**：MCP `agent_dispatch` 是Trae面板与天机内核交互的核心入口，必须能识别全部Agent才能正确路由。

**How**：
1. 在 `AgentFrameworkServer.__init__` 中调用新的 `_load_agent_capabilities()` 方法。
2. `_load_agent_capabilities` 读取 `_AGENT_REGISTRY.json`，将每个Agent的 `capabilities` 和 `keywords`（从prompt或配置中提取）构建为调度匹配字典。
3. 保留原有23个天机Agent的keywords作为基础，补充7个官方Agent的keywords。

---

### Change 4: 路由策略支持多源Agent与科学调度

**文件**：`core/routing/agent_strategy.py`

**What**：
- 修改 `AgentRoutingStrategy` 默认使用 `CapabilityRegistry`（即 `_AGENT_REGISTRY.json`）作为矩阵源。
- 支持任务字段 `source_filter`：可限定只在 `tianji`、`trae-official`、`trae-builtin` 中调度。
- 增强 `_match_by_text`：
  - 不仅匹配 `capabilities`，还匹配 `inter_agent_calling.when_to_call` 中的描述。
  - 引入TF-IDF/关键词权重，提升UI设计、API测试等专业Agent的匹配精度。
- 当任务类型明确为内置Agent功能（如 `codebase_chat`、`end_to_end_task`）时，直接路由到 `trae-chat` 或 `trae-agent`。
- 新增 `TopologyClassifier` 调用：在任务分解后，根据DAG形状推荐协作模式。
- 新增 `LearningRouter` 集成：对高频任务使用历史最优路由策略。

**Why**：使 `AgentRoutingStrategy` 从"仅天机Agent"升级为"全Agent统一路由"，并具备科学调度能力。

**How**：
1. 在 `AgentRoutingStrategy.__init__` 中默认构造 `CapabilityRegistry()`。
2. 扩展 `route()` 方法，加入 `source_filter` 和 `topology_hint` 处理逻辑。
3. 增加 `_extract_keywords_from_task(task)` 辅助函数，合并 `task_type`、`goal`、`keywords`、`content`。

---

### Change 5: 调度编排器暴露全Agent API与Workflow支持

**文件**：`core/orchestration/agent_orchestrator.py`、`core/orchestration/api_exposure.py`

**What**：
- `AgentScheduler.get_summary()` 返回的统计信息包含全部Agent列表（31+2）。
- 新增方法 `list_all_agents()`：返回天机、官方、内置三类Agent的元数据。
- 新增方法 `design_workflow()`：为复杂任务生成MCP Workflow Blueprint。
- 新增方法 `run_workflow()`：执行已存储的workflow blueprint。
- `api_exposure.py` 中暴露新端点：
  - `GET /api/orchestrator/agents`：列出全部Agent。
  - `GET /api/orchestrator/agents/{agent_id}`：查询单个Agent详情。
  - `POST /api/orchestrator/agents/dispatch`：统一调度接口，支持任意Agent。
  - `POST /api/orchestrator/workflows/design`：设计工作流蓝图。
  - `POST /api/orchestrator/workflows/{blueprint_id}/run`：执行工作流蓝图。

**Why**：为Trae面板和外部系统提供完整的Agent发现、调度和workflow编排API。

**How**：
1. 在 `AgentScheduler` 中注入 `CapabilityRegistry`、`WorkflowBlueprintManager`、`TopologyClassifier`。
2. 在 `api_exposure.py` 中新增 FastAPI 路由函数。
3. 复用现有 `agent_dispatch` 和 `dispatch_parallel` 逻辑。

---

### Change 6: A2A网关暴露官方与内置Agent卡片

**文件**：`core/orchestration/a2a_gateway.py`

**What**：
- 在A2A AgentCard生成逻辑中，从 `CapabilityRegistry` 读取全部Agent。
- 为每个Agent生成标准A2A AgentCard，包含：
  - `name`、`description`、`capabilities`、`skills`。
  - `source` 字段（tianji / trae-official / trae-builtin）。
  - `authentication` 字段（基于天机安全聚阵的权限矩阵）。
- 内置Agent `trae-chat` 和 `trae-agent` 生成特殊卡片，说明其为Trae IDE内置入口。
- 实现A2A Task生命周期状态机，支持 `submitted → working → input-required → completed/failed/canceled`。

**Why**：A2A是跨平台互操作标准，必须覆盖全部Agent才能实现与外部系统的完整互操作。

**How**：
1. 在A2A网关初始化时加载 `CapabilityRegistry`。
2. 新增 `_generate_agent_card(agent_id, meta)` 方法。
3. 暴露 `GET /.well-known/agent-card.json?agent={agent_id}` 端点（如已有端点则扩展）。
4. 实现 `POST /a2a/tasks/send` 和 `POST /a2a/tasks/sendSubscribe` 端点。

---

### Change 7: 新增科学调度组件

#### 7.1 WorkflowBlueprintManager

**文件**：`core/orchestration/workflow_blueprint.py`

**职责**：
- 定义workflow blueprint schema（基于MCP Workflow Engine五原语：call、map、reduce、loop、condition）。
- 提供blueprint存储、版本控制、执行引擎。
- 与 `mcp_bridge.py` 集成，将blueprint转换为实际MCP工具调用。

#### 7.2 TopologyClassifier

**文件**：`core/orchestration/topology_classifier.py`

**职责**：
- 分析任务DAG的并行宽度、关键路径深度、子任务耦合度。
- 输出推荐协作模式（A/B/C/D/E/F）和置信度。

#### 7.3 StageScheduler

**文件**：`core/orchestration/stage_scheduler.py`

**职责**：
- 将任务DAG划分为链式阶段和Map-Reduce阶段。
- 可选MILP优化器（使用 `pulp` 或 `scipy.optimize`）。
- 管理阶段间数据管道和同步屏障。

#### 7.4 LearningRouter

**文件**：`core/orchestration/learning_router.py`

**职责**：
- 从L3 Episodic读取历史调度轨迹。
- 维护Agent选择的成功率和成本统计。
- 对高频任务提供基于经验的最优路由推荐。

---

### Change 8: 验证与回归测试

**文件**：`tests/`（新增或复用现有测试）

**What**：
- 新增单元测试 `tests/core/orchestration/test_registry_loader.py`：
  - 验证 `_AGENT_REGISTRY.json` 能正确加载31个自定义Agent。
  - 验证内置Agent `trae-chat`、`trae-agent` 被正确注入。
  - 验证 `CapabilityRegistry.find_by_capability` 对官方Agent有效。
- 新增单元测试 `tests/mcp/test_agent_framework_dispatch.py`：
  - 验证 `agent_dispatch` 对UI设计、API测试、性能优化等任务的调度推荐包含官方Agent。
  - 验证内置任务（如"代码库问答"）路由到 `trae-chat`。
- 新增单元测试 `tests/core/orchestration/test_topology_classifier.py`：
  - 验证不同DAG形状映射到正确的协作模式。
- 新增集成测试 `tests/core/orchestration/test_scheduler_api.py`：
  - 验证 `/api/orchestrator/agents` 返回33个Agent。
  - 验证 `/api/orchestrator/agents/dispatch` 能调度官方Agent。
  - 验证 `/api/orchestrator/workflows/design` 能生成workflow blueprint。
- 新增CLEAR评估测试 `tests/core/orchestration/test_clear_metrics.py`：
  - 验证成本、延迟、效能、安全、可靠性五维指标可采集。

**Why**：确保优化不破坏现有调度逻辑，且新增能力真实可用，并满足CLEAR科学评估标准。

**How**：
1. 使用 pytest 编写测试。
2. 对需要文件系统的测试使用临时 `_AGENT_REGISTRY.json` 副本。
3. 运行 `pytest tests/core/orchestration tests/mcp -v` 验证。

---

## Part IV: 实施阶段与里程碑

### Phase 1: 基础对齐（命名+注册表统一）

**目标**：完成命名规范、能力矩阵、MCP调度基础统一。

| 任务 | 负责人 | 交付物 |
|------|--------|--------|
| 更新AGENT-NAMING-V3.md | @wenzong | v4.2命名规范文档 |
| 重构registry.py | @tianshu | CapabilityRegistry统一加载 |
| 更新agent_framework.py | @tianshu | 33个Agent调度识别 |
| 更新agent_strategy.py | @jingwei | 多源Agent路由+TopologyClassifier |
| 回归测试 | @tiewei | Phase 1测试通过报告 |

**Gate**：
- `GET /api/orchestrator/agents` 返回33个Agent。
- `agent_dispatch` 对7类官方任务推荐官方Agent。

### Phase 2: 科学调度层构建

**目标**：引入SKYAPI、AdaptOrch、Uno-Orchestra的核心机制。

| 任务 | 负责人 | 交付物 |
|------|--------|--------|
| 实现TopologyClassifier | @jingwei | topology_classifier.py |
| 实现StageScheduler | @tiansuan | stage_scheduler.py |
| 实现LearningRouter | @tiansuan | learning_router.py |
| 集成CLEAR指标采集 | @qianli | clear_metrics.py |
| 回归测试 | @tiewei | Phase 2测试通过报告 |

**Gate**：
- 任务DAG能自动映射到6种协作模式。
- CLEAR五维指标可采集并输出。

### Phase 3: Workflow Engine与A2A增强

**目标**：实现MCP Workflow Engine智能-执行分离，完善A2A互操作。

| 任务 | 负责人 | 交付物 |
|------|--------|--------|
| 实现WorkflowBlueprintManager | @gongzao | workflow_blueprint.py |
| 扩展agent_orchestrator API | @tianshu | workflow相关端点 |
| 完善A2A网关 | @zhenshan | Agent Card + Task生命周期 |
| 安全审计 | @zhenshan | A2A安全加固报告 |
| 回归测试 | @tiewei | Phase 3测试通过报告 |

**Gate**：
- `/api/orchestrator/workflows/design` 能生成可执行的blueprint。
- A2A Agent Card暴露全部33个Agent。
- 安全审计无Critical/Major漏洞。

### Phase 4: 验证、固化与经验沉淀

**目标**：通过CLEAR评估，固化最佳实践，沉淀到记忆系统。

| 任务 | 负责人 | 交付物 |
|------|--------|--------|
| CLEAR综合评估 | @tiewei | CLEAR评估报告 |
| 性能基准测试 | @zhuiguang | 性能基准报告 |
| 经验沉淀 | @huasheng | L4 Semantic经验库更新 |
| 文档归档 | @shiguan | 归档INDEX |

**Gate**：
- CLEAR综合评分 >= 9.9。
- 无新增测试失败。
- 经验库完成更新。

---

## Assumptions & Decisions

1. **权威数据源**：`_AGENT_REGISTRY.json` 是Agent元数据的唯一权威源，运行时不再维护硬编码副本。
2. **内置Agent处理**：Trae内置的 `Chat` 和 `Agent` 不创建 `trae-official-*.json` 文件，而是作为虚拟Agent通过 `CapabilityRegistry` 注入，避免与Trae IDE冲突。
3. **向后兼容**：`AGENT_CAPABILITY_MATRIX` 全局变量继续存在，但其内容由 `_AGENT_REGISTRY.json` 驱动；依赖它的旧代码无需修改。
4. **最小改动原则**：不修改Trae IDE本身的配置或行为，只优化天机侧的运行时和文档。
5. **中文名统一**：Trae官方Agent的中文名已确定为：UI设计师、前端架构师、后端架构师、API测试专家、AI集成工程师、性能优化专家、合规检查专家。
6. **科学评估优先**：所有调度优化必须以CLEAR五维指标为衡量标准，避免仅追求单一成功率。
7. **渐进式引入MCP Workflow Engine**：先从高频、确定性任务开始沉淀blueprint，再逐步扩展到复杂任务。

---

## Verification Steps

### 文档验证
- 打开 `.trae/agents/AGENT-NAMING-V3.md`，确认包含24+7+2共33个Agent命名表。
- 确认版本号为 v4.2，生效日期为当前日期。

### 配置验证
- 运行脚本验证 `_AGENT_REGISTRY.json` 中31个Agent的 `name` 与7个官方配置文件一致。
- 确认 `trae-official-*.json` 的 `basic_info.name` 为中文。

### 运行时验证
- 启动天机v9.1服务。
- 调用 `GET /api/orchestrator/agents`，期望返回33个Agent（31自定义+2内置）。
- 调用 `agent_dispatch` tool，任务类型为 `"设计一个登录页面"`，期望推荐包含 `ui_designer`。
- 调用 `agent_dispatch` tool，任务类型为 `"进行代码库问答"`，期望推荐 `trae-chat`。
- 调用 `POST /api/orchestrator/workflows/design`，期望返回有效的workflow blueprint JSON。

### 科学调度验证
- 构造一个线性依赖任务DAG，验证推荐模式为A-串行流水线。
- 构造一个全独立子任务集合，验证推荐模式为B-并行分析。
- 构造一个扇出+聚合任务，验证推荐模式为C-层级分解。

### CLEAR评估验证
- 运行10次典型调度任务，采集：
  - 平均token消耗、API调用次数
  - 平均端到端延迟
  - 任务完成率
  - 安全/合规通过率
  - 多次运行一致性
- 计算CLEAR综合评分，验证 >= 9.9。

### 测试验证
- 运行 `pytest tests/core/orchestration/test_registry_loader.py tests/mcp/test_agent_framework_dispatch.py tests/core/orchestration/test_scheduler_api.py tests/core/orchestration/test_topology_classifier.py tests/core/orchestration/test_clear_metrics.py -v`。
- 期望所有测试通过，覆盖率不低于80%。

### 回归验证
- 运行现有调度相关测试 `pytest tests/core/orchestration tests/core/routing -v`，无新增失败。
- 检查 `core/orchestration/dispatcher.py` 和 `core/orchestration/pipeline.py` 的导入无循环依赖。

---

## References

1. Parmar, A. S. (2026). *Separating Intelligence from Execution: A Workflow Engine for the Model Context Protocol*. arXiv:2605.00827. https://arxiv.org/abs/2605.00827
2. Wang, P. (2025). *SKYAPI: Structural-Aware Orchestration for LLM-Based Multi-Agent Systems*. University of Illinois Urbana-Champaign. https://hdl.handle.net/2142/132596
3. Cui, Z. et al. (2026). *Uno-Orchestra: Parsimonious Agent Routing via Selective Delegation*. arXiv:2605.05007. https://arxiv.org/abs/2605.05007
4. Yu, G. (2026). *AdaptOrch: Task-Adaptive Multi-Agent Orchestration in the Era of LLM Performance Convergence*. arXiv:2602.16873. https://arxiv.org/abs/2602.16873
5. Mehta, S. (2025). *Beyond Accuracy: A Multi-Dimensional Framework for Evaluating Enterprise Agentic AI Systems*. arXiv:2511.14136. https://arxiv.org/abs/2511.14136
6. Microsoft Developer Community Blog (2025). *Orchestrating Multi-Agent Intelligence: MCP-Driven Patterns in Agent Framework*. https://techcommunity.microsoft.com/blog/azuredevcommunityblog/orchestrating-multi-agent-intelligence-mcp-driven-patterns-in-agent-framework/4462150
7. Temporal Blog (2025). *Orchestrating ambient agents with Temporal*. https://temporal.io/blog/orchestrating-ambient-agents-with-temporal
8. Habler, I. et al. (2025). *Building A Secure Agentic AI Application Leveraging Google's A2A Protocol*. arXiv:2504.16902. https://arxiv.org/abs/2504.16902
9. Google A2A Protocol. https://a2aprotocol.ai/
10. Jyothi, B. et al. (2025). *Model Context Protocol (MCP) Server for Multi-Agent AI Assistants with Persistent Memory*. Engineering Research.
11. Mohammadi, M. et al. (2025). *Evaluation and Benchmarking of LLM Agents: A Survey*. KDD '25. https://arxiv.org/abs/2507.21504
12. TrustOrch (2025). *A Dynamic Trust-Aware Orchestration Framework for Adversarially Robust Multi-Agent Collaboration*. https://www.preprints.org/manuscript/202512.2487
13. CardinalHQ (2025). *Why MCP Beats Integrations: The API Standard Built for AI-Native SaaS*. https://cardinalhq.io/blog/api-ai-native-saas

---

**版本**: v4.2.0 | **生效日期**: 2026-07-02 | **维护**: @tianshu + @jingwei + @tiansuan
**升级要点**: 
- 新增Part I科学基础，系统吸收MCP Workflow Engine、SKYAPI、Uno-Orchestra、AdaptOrch、CLEAR等最新技术资源。
- 新增三层科学智能调度架构（智能优化层、编排执行层、Agent资源层）。
- 新增WorkflowBlueprintManager、TopologyClassifier、StageScheduler、LearningRouter四大组件。
- 将CLEAR五维评估框架集成到调度系统优化目标中。
- 明确Phase 1~4实施阶段与Gate门禁。
