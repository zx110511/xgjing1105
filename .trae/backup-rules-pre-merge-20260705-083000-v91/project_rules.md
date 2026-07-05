---
alwaysApply: true
description: 天机v10.0.1统一规则 - 每次对话自动加载，6规则体系，涵盖宪法+智能体+质量+操作+开发+常识
---

# 天机v10.0.1 统一规则 (Tianji Unified Rules) v3.0

> 本文件是每次对话自动加载的入口规则文件。
> 详细规范参见 .trae/rules/ 下6个核心规则文件。
>
> **规则体系**: 01-天机宪法v6.0 + 02-智能体法则v4.0 + 03-质量法则v4.0 + 04-操作法则v4.0 + 05-开发法则体系v2.0 + 06-常识类法则v2.0
>
> **开发根目录**: D:\元初系统\天机v10.0系列
> **运行基线**: D:\元初系统\天机v9.1 (后台运行，记忆存储所在地)
> **补充参考**: D:\元初系统\天机v8.1 (有益补充，增量开发)
> **概念基线**: D:\元初系统\灵境\道 (九域四十地煞定义)

---

## 0. 对话生命周期必做清单 (P0-最高优先级·强制执行)

> **本节为最高优先级规则，凌驾于所有其他规则之上。**
> Trae IDE不支持lifecycle hooks，所以Agent必须在对话开始/结束前**自觉执行**以下清单。
> 未执行 = P0违规 = 信任降级。

### 0.1 对话开始必做清单 (用户发送消息后立即执行)

```
Step 1: 感知系统状态
  └── 调用 tianji_health 确认天机8771服务可用
      ├── healthy → 继续 Step 2
      └── unhealthy → TVP声明降级，使用离线队列

Step 2: 检索相关记忆 (非trivial决策)
  └── 调用 memory_recall(query=用户消息关键内容, layers=["L3","L4"], limit=5)
      ├── 有相关记忆 → 融合到上下文
      └── 无相关记忆 → 标记为新场景

Step 3: 任务复杂度判断 (强制)
  ├── complexity=trivial → 直接执行，跳过Step 4-5
  ├── complexity=standard → 进入Step 4
  └── complexity=critical → 进入Step 4 + 人工确认

Step 4: 智能调度 (复杂度≥standard时强制)
  └── 调用 agent_dispatch(task_type, complexity, priority, required_agents)
      ├── 推荐可用 → TVP声明切换到推荐Agent
      └── 推荐不可用 → 降级为@tianshu直接执行 + TVP声明

Step 5: 规则合规验证 (复杂度=critical时强制)
  └── 调用 rule_evaluate(rules=["01-天机宪法","02-智能体法则"], context=任务)
```

### 0.2 对话结束必做清单 (回复用户前必须完成)

```
Step 1: 对话内容完整归档 (强制·4要素·MCP优先)
  └── 方式A (推荐): Agent调用MCP memory_remember (含TCL归一化+quality_gate+FTS5)
      ├── L3 Episodic: 4要素合并为一条 (content=3-5KB, tags含full-capture)
      ├── L4 Semantic: 每个文件变更一条 (content=200-500B)
      ├── L5 Meta: critical级系统决策一条 (仅complexity=critical)
      ├── 调用3次 memory_remember (或最多N+2次, N=文件数)
      └── 失败降级: 写入离线队列 .tianji/offline_writes.json

  方式B (降级): python scripts/agent_archive.py <input.json>
      ├── 独立脚本,绕过MCP TCL管道, 无TCL归一化
      └── MCP不可用或Agent无法调用MCP时使用

  归档规范(取代摘要式归档):
  - 信息密度: 100% (完整记录,不摘要化)
  - 必填要素: 4要素缺一不可(无文件变更时file_changes=[])
  - 幂等性: content_hash去重
  - 编码: UTF-8全链路安全
  - 性能: MCP单次0.3-1s, 方式B单次POST 0.1-0.5s

Step 2: 文件变更同步 (由Step1自动完成)
  └── 每个文件变更自动写入L4 Semantic层
      tags: ["file-sync","full-capture","session:{id}","file:{basename}"]

Step 3: 系统级决策归档 (由Step1自动完成,仅critical级)
  └── complexity=critical时自动写入L5 Meta层
      tags: ["system-decision","full-capture","session:{id}"]

Step 4: 对话自动审计 (强制)
  ├── 检查项1: agent_archive.py返回l3_id非空
  ├── 检查项2: 所有file_changes都有对应l4_ids
  ├── 检查项3: critical级任务返回l5_id非空
  └── 检查项4: offline_queued=0 + errors=[] (无错误)
```

### 0.2.1 方式B归档工具 (agent_archive.py) v2.1 — 独立降级脚本

```
位置: scripts/agent_archive.py (独立Python脚本)
定位: Agent无法调用MCP时的独立降级方案
调用: python scripts/agent_archive.py <JSON输入文件> [-v]

输入JSON格式:
{
  "session_id": "session-001",          // 必填
  "user_message": "完整用户消息原文",     // 必填: 要素1
  "agent_response": "完整Agent回复原文",  // 必填: 要素2
  "agent_id": "tianji",                 // 可选, 默认tianji
  "complexity": "standard",             // 可选: trivial/standard/critical
  "decisions": [                        // 可选: 要素3
    {"step": "...", "agent": "...", "decision": "...", "reason": "...", "evidence": "..."}
  ],
  "file_changes": [                     // 可选: 要素4
    {"path": "xxx.py", "type": "create|modify|delete", "lines": 280, "summary": "..."}
  ],
  "mcp_tools": ["tianji_health"],       // 可选
  "tvp_declarations": ["[TVP] ..."]      // 可选
}

输出JSON:
{
  "l3_id": "abc123",           // L3 Episodic记忆ID
  "l4_ids": ["def456", ...],   // L4 Semantic记忆ID列表
  "l5_id": "ghi789",           // L5 Meta记忆ID(仅critical级)
  "session_id": "...",
  "hash": "...",
  "offline_queued": 0,
  "errors": []
}
```

### 0.2.2 归档器集成路径 (辅助组件·v3.2)

```
桌面快捷方式 C:\Users\Administrator\Desktop\天机v9.1.lnk
  └── start_tianji.bat
      └── launcher/tianji_v91_launcher.py
          └── server/main.py
              └── server/api/conversation_archive_routes.py
                  └── core/memory/conversation_archiver.py
                      ├── POST /api/conversation/archive (单轮归档)
                      ├── POST /api/conversation/session (会话归档)
                      ├── GET  /api/conversation/stats (统计)
                      ├── GET  /api/conversation/recent (最近归档)
                      ├── POST /api/conversation/sync_offline (同步离线队列)
                      └── GET  /api/conversation/health (健康检查)

启动验证: launcher._CHAIN_ENDPOINTS 包含 conversation_archiver 端点
```

### 0.3 复杂度判断矩阵 (强制参考)

| 任务特征 | complexity | 必做 |
|---------|-----------|------|
| 单步操作/无依赖/无风险 | trivial | 仅Step 1+归档 |
| 多步操作/有依赖/低风险 | standard | 完整5步流程 |
| 多步操作/高风险/不可逆 | critical | 5步+人工确认+L5归档 |
| 涉及≥2个Agent | 强制standard+ | 必须agent_dispatch |
| 涉及架构决策 | 强制critical | 必须三工具联合 |
| 涉及故障追溯 | 强制critical | 必须 memory_recall+反思环 |

### 0.4 MCP工具必然使用矩阵 (强制参考)

| 任务类型 | 必用MCP工具 | 触发条件 | 豁免 |
|---------|------------|---------|------|
| 非平凡决策 | `memory_recall` | complexity≠trivial | 无 |
| 任何写操作 | `memory_remember` | 文件修改/系统变更 | 无 |
| 多Agent任务 | `agent_dispatch` | 涉及≥2个Agent | 无 |
| 规则变更 | `rule_evaluate` | 架构/规则变更 | 无 |
| 故障发生 | `memory_recall`+反思环 | 系统异常 | 无 |
| 推演深度≥6 | `WebSearch` | 复杂架构推演 | 无 |

### 0.5 违规处理

- 单次未执行对话结束归档 → P0违规，下次对话开始时补归档
- 连续3次未执行 → 信任降级，标记为"不可靠Agent"
- 影响系统稳定性 → P0违规 + 触发进化反思环

---



## 1. 系统身份

```
系统: 天机 (Tianji Memory Engine) v10.0.1
概念宪法: 天机统一概念体系v3.1
开发根目录: D:\元初系统\天机v10.0系列
运行基线: D:\元初系统\天机v9.1 (后台运行，记忆存储+智能体调度全量工作)
补充参考: D:\元初系统\天机v8.1 (有益补充，增量开发，绝不做减量)
概念基线: D:\元初系统\灵境\道 (九域四十地煞二十二天罡定义)
语言栈: Python 3.12 / Node.js 24 / TypeScript strict
服务端口: 8771 (v9.1运行) / 8772 (v10.0.1开发目标)
```

核心路径 (全部相对于开发根目录 D:\元初系统\天机v10.0系列):

```
.tianji/                   → 运行时状态 (离线队列等)
天机v10.0.1 实现集/         → 规划+任务+标准+补齐文档
  ├── README.md            → [L4] 实现集导航
  ├── 规划/ + README.md    → 宏观/中观/微观规划 + 概念宪法v3.1
  ├── 任务/ + README.md    → Phase-A~H 任务卡 + 总表 + 执行手册
  ├── 标准/ + README.md    → 执行/测试/审计/灵魂拷问/增量开发标准
  ├── 补齐/ + README.md    → v8.1增量/存储边界/文件同步/对话记录/记忆迁移
  └── 科研资源/ + README.md → 技术资源报告
src/                       → v10.0.1 代码根
  ├── README.md            → [L4] 代码架构导航
  ├── mem/ + README.md     → MEM记忆聚阵 (D1守道域)
  ├── sto/ + README.md     → STO存储聚阵 (D2+D12)
  ├── knw/ + README.md     → KNW知识聚阵 (D2图枢)
  ├── evo/ + README.md     → EVO进化聚阵 (D3+D4)
  ├── sec/ + README.md     → SEC安全聚阵 (D5+D9)
  ├── agt/ + README.md     → AGT Agent聚阵 (D6)
  ├── orc/ + README.md     → ORC编排聚阵 (D8)
  ├── evt/ + README.md     → EVT事件聚阵 (D13)
  ├── ops/ + README.md     → OPS运维聚阵 (D7)
  └── shared/ + README.md  → 共享内核 (D10横切)
tests/ + README.md         → 测试套件
docs/ + README.md          → 文档
```

参考基线路径 (只读参考):

```
v9.1 (D:\元初系统\天机v9.1): 86+核心模块 / 38 Protocol / 记忆全链运行
v8.1 (D:\元初系统\天机v8.1): 独有模块补充 / 增量开发参考
灵境/道 (D:\元初系统\灵境\道): 九域四十地煞 / 975 [v10-ready]
```

---

## 2. Trae依托法则 (铁律)

**Trae IDE依托天机v9.1开发天机v10.0.1，规则系统(.trae/rules)是Trae工作的根本法则。**

```
Trae IDE (开发工具)
  ├── 依托: 天机v9.1 (运行基线) — 记忆存储+智能体调度+MCP服务
  ├── 产出: 天机v10.0.1 (开发目标) — 所有新代码写入天机v10.0系列
  └── 参考: 灵境/道 + 天机v8.1 — 概念宪法+增量补充
```

**强制约束**:
- v9.1不可用时，开发工作降级，离线队列暂存操作记录
- 规则系统(.trae/rules)是Trae工作的根本法则，重建/变更必须同步更新规则
- **规则未更新 = 工作未完成**

---

## 3. 双存储系统 (铁律)

| 维度 | v9.1 (运行基线) | v10.0.1 (开发目标) |
|------|----------------|-------------------|
| 数据库 | v9.1/data/icme.db | v10.0系列/data/icme.db (规划) |
| 端口 | 8771 | 8772 (规划) |
| 角色 | 开发期记忆服务 | 独立新系统存储 |

- 开发期间，v10.0.1的记忆操作通过v9.1的MCP服务执行
- v10.0.1独立运行后，两个存储系统完全独立
- 禁止混淆两个存储系统的数据边界

---

## 4. 四源关系 (铁律)

```
灵境/道 (概念基线) -- 九域四十地煞二十二天罡定义，概念权威源
v9.1 (运行基线) -- 后台持续运行，记忆存储+智能体调度+记忆全链全量工作
v8.1 (有益补充) -- v9.1非最全最优，v8.1有独有模块可参考，增量开发
v10.0.1 (开发目标) -- 完全独立新系统，在天机v10.0系列下构建
```

**关键约束**:
- 记忆存储在v9.1: v9.1后台运行提供记忆全链服务
- v8.1不放弃: 增量开发，绝不做减量
- 禁止在v8.1/v9.1修改代码作为开发产出
- 所有新代码写入 `D:\元初系统\天机v10.0系列\`

### README体系 (灵魂框架)

- 有一个文件夹，必然有一个README.md
- 每个README.md包含6大标准区块: 身份锚点 / 职责声明 / 结构索引 / 联动关系 / 灵魂拷问 / 变更日志
- README之间严格联动: 上级引用下级，下级声明上级
- README与记忆系统完整对齐: 每个README映射一个记忆层级

---

## 5. 天机记忆系统 (ICME六层架构)

| 层级 | 名称       | 容量上限 | 固结间隔 | 用途             |
| ---- | ---------- | -------- | -------- | ---------------- |
| L0   | sensory    | 10MB     | 30s      | 原始输入缓存     |
| L1   | working    | 50MB     | 60s      | 会话上下文       |
| L2   | short_term | 100MB    | 120s     | 关键信息保持     |
| L3   | episodic   | 500MB    | 300s     | 决策记录/AI经验  |
| L4   | semantic   | 2GB      | 600s     | 知识图谱/概念    |
| L5   | meta       | 100MB    | 900s     | 策略自优化(顶端) |

### 记忆操作优先级 (Memory-First) — P0强制

```
Step 1: tianji_intercept(user_input) -> enhanced_input
Step 2: 基于 enhanced_input 生成回复
Step 3: memory_remember(content, layer, tags) / 离线队列(降级时)
```

### 操作必记录 — P0强制

```
写操作前 -> L1 Working (意图+参数)
写操作后 -> L3 Episodic (结果+影响)
系统变更 -> L5 Meta (策略归档)
```

---

## 6. 六大根本原则

### 原则1: 记忆优先决策
- 非平凡决策必须查询天机 (L4知识+L3经验+L5约束)
- 豁免: 仅限简单配置选择 (complexity=low)

### 原则2: 操作必记录
- 写操作前 -> L1 Working / 操作后 -> L3 Episodic / 系统变更 -> L5 Meta

### 原则3: 故障必回溯
- 即时 -> L0捕获 / 根因 -> L3记录 / 教训 -> L4沉淀

### 原则4: 破除闭门造车 (P0)
- 推演深度>=6分: 必须联网搜索+天机记忆资源
- 推演深度>=4分: 必须提取天机记忆参考

### 原则5: 灵魂拷问通用化 (P0)
- 六维验证: 可实现性/真实场景/并发稳定/跨模块集成/兼容性/边界条件
- 评分门槛: >=9.95分 (满分10分)

### 原则6: 对话自动审计 (P0)
- 审计清单: 决策记录/文件内容/错误修复/待办更新
- 审计不通过则补充记录

---

## 7. 规则体系索引 (v3.0 - 精简强壮化)

| 文件 | 职责 | 核心内容 | 版本 |
|------|------|---------|------|
| 01-天机宪法v6.0.md | 系统根基 | 身份+四源+路径+README+记忆+依托+双存储+六原则+强制约束 | v6.0 |
| 02-智能体法则v4.0.md | 智能体调度+协作 | 权限矩阵+TVP+六大协作+事件驱动+工业化生产小说+经验复用+MCP必然使用+智能调度必然执行 | v4.0 |
| 03-质量法则v4.0.md | 质量+MCP规范 | 质量红线+灵魂拷问+Stage Gate+MCP规范使用+参数验证+频率限制 | v4.0 |
| 04-操作法则v4.0.md | 决策+降级+同步 | 六步决策+四级降级+离线队列+三道防线+对话记录 | v4.0 |
| 05-开发法则体系v2.0.md | 开发法则+经验复用 | 20条法则+四维时空+经验库架构+经验复用流程+强制规则 | v2.0 |
| 06-常识类法则v2.0.md | 常识+MCP常识化 | 8大常识+TVP-MCP声明+参数验证+频率限制+错误响应+检查表 | v2.0 |

**精简成果**: 从7个文件精简为6个核心文件，强壮存留规则+法则

---

## 7.5 规则五类分层体系 (v3.1 - 智能规则分层·新增)

**核心原则**: 简化=强化。通过分层激活，实现"始终生效规则最小化+智能生效规则精准化"。

### 分层架构

| 规则类别 | 激活条件 | 包含文件 | 核心目标 |
|---------|---------|---------|---------|
| **A-始终生效规则** | 每次对话自动加载 | 01天机宪法 + 06常识类法则 | 系统根基+常识基线·不可降级 |
| **B-智能生效规则** | 任务匹配时激活 | 02智能体法则(第12-13条) + 03质量法则(MCP规范) | MCP必然使用+智能调度必然执行 |
| **C-编程规则** | 代码开发任务激活 | 05开发法则体系 + 04操作法则(决策+降级) | 开发流程+决策流水线+故障降级 |
| **D-工业化小说生产规则** | 小说创作任务激活 | 02智能体法则(第七条S0-S6) + 小说工厂.trae/rules | 工业化生产流程+Stage Gate+经验复用 |
| **E-通用规则** | 跨场景通用 | 04操作法则(对话记录) + 03质量法则(灵魂拷问) | 对话审计+质量验证+记忆操作 |

### 激活判定矩阵

| 任务类型 | 激活规则类别 | 必然执行 |
|---------|------------|---------|
| 普通对话 | A+E | 常识+对话审计 |
| 代码开发 | A+B+C+E | MCP必然使用+智能调度+开发流程+决策流水线 |
| 小说创作 | A+B+D+E | MCP必然使用+智能调度+工业化流程+质量验证 |
| 架构决策 | A+B+C+E | 三工具联合(dispatch+recall+evaluate)+Stage Gate |
| 故障追溯 | A+B+F(进化闭环) | memory_recall+反思环+经验沉淀 |
| 系统运维 | A+B+C+E | agent_dispatch+rule_evaluate+部署验证 |

### 必然使用效果强化（铁律）

**MCP技能必然使用** (02-智能体法则v4.0 第十二条):
- 非平凡决策 → `memory_recall` (P0强制)
- 写操作 → `memory_remember` (P0强制)
- 多Agent任务 → `agent_dispatch` (P1强制)
- 规则变更 → `rule_evaluate` (P1强制)
- 推演深度≥6 → WebSearch (P1强制)

**智能调度必然执行** (02-智能体法则v4.0 第十三条):
- ≥2个Agent → `agent_dispatch` (P1强制)
- 复杂度≥medium → `agent_dispatch`+`memory_recall` (P1强制)
- 优先级≥high → `agent_dispatch`+`rule_evaluate` (P1强制)
- 架构决策 → 三工具联合 (P1强制)

**违规处理**: 连续3次违规 → 信任降级 → 影响系统稳定性 → P0违规

---

## 8. MCP工具速查

### 核心工具 (memory-engine-global)
```
tianji_intercept / memory_remember / memory_recall / memory_forget
memory_consolidate / tianji_health / tianji_auto_tag / tianji_summarize
tianji_semantic_search / search_memories / memory_stats / memory_capacity
```

### 调度工具 (agent-framework-global)
```
context_extract / agent_dispatch / rule_evaluate / system_status
```

### MCP调用规范 (TVP-MCP声明)
```
[TVP-MCP] 工具: {tool_name} | Server: {server_name} | 参数: {key_params} | 目的: {purpose}
```

### 调用优先级
1. tianji_health (每次启动)
2. memory_recall / memory_remember (决策参考/结果记录)
3. agent_dispatch (多Agent协作)
4. 其余按需

---

## 9. 编码规范 — P0强制

- Python: 类型注解>=80% / docstring必须 / 圈复杂度<=10 / snake_case / UTF-8-SIG
- TypeScript: strict=true / noImplicitAny=true / camelCase
- 通用禁止: 硬编码密码/token/PII / `any`类型 / `eval()`/`exec()` / 忽略错误

---

## 10. 故障降级速查

| 级别 | 触发 | 影响 | 恢复 |
|------|------|------|------|
| L0 正常 | 天机healthy | 无 | - |
| L1 缓存 | 写入超时/失败 | ~10%下降 | 离线队列+稳定60s |
| L2 启发 | 天机不可用>5min | ~30%下降 | 规则驱动+稳定5min |
| L3 保守 | 天机不可用>30min | ~60%缩减 | 人工确认+逐级回升 |

恢复: 严禁跳级，L3→L2→L1→L0逐级回升，每级5分钟。

---

## 11. 四个升级方向实现

### 方向1: 智能体智能调度规范
- 实现: 02-智能体法则v4.0.md
- 内容: 事件驱动架构+熔断机制+决策归属+Stage Gate责任矩阵

### 方向2: MCP规范使用
- 实现: 03-质量法则v4.0.md + 06-常识类法则v2.0.md
- 内容: MCP工具优先级矩阵+TVP-MCP声明+参数验证+频率限制+错误分级响应

### 方向3: 工业化生产小说
- 实现: 02-智能体法则v4.0.md
- 内容: S0→S6流程+关键约束+Agent归属+质量门禁

### 方向4: 经验复用机制
- 实现: 02-智能体法则v4.0.md + 05-开发法则体系v2.0.md
- 内容: 经验库架构(L4 Semantic)+经验复用流程+强制规则+演化周期

---

**版本**: 3.0.0 | **生效**: 2026-06-25 | **维护**: @tianshu + @yiku
**精简成果**: 7文件→6文件，强壮存留规则+法则
**升级方向**: 智能体调度+MCP规范+工业化生产小说+经验复用
