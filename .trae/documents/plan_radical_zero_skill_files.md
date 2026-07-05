# 激进精简：零技能文件架构规划

**版本**: v1.0
**状态**: 待审批
**类型**: 架构重构

---

## 一、问题诊断

### 现状
- 39个MCP协议工具 ↔ 39个Trae技能文件，机械一一对应
- 技能文件 = MCP工具的"使用说明书"
- 两套系统需要同步维护，一致性难以保证

### 根本问题
技能文件是**冗余的中间层**——它们的全部价值可以被更底层的机制完全替代。

---

## 二、核心论断

> **技能文件的每一项价值，都有一个更权威、更可靠、更自进化的底层机制可以替代。**

| 技能文件提供的价值 | 替代机制 | 为什么更好 |
|-------------------|---------|-----------|
| 触发场景判断 | Agent能力声明 + 调度规则 | 统一数据源，自动路由 |
| 执行步骤指导 | MCP工具schema + description | 随工具版本同步，永不脱节 |
| 最佳实践与陷阱 | L4 Semantic经验沉淀 | 自进化，越用越好 |
| 协作伙伴关系 | AMIM能力矩阵 + 权限矩阵 | 单一真相源，动态更新 |
| 质量标准 | Stage Gate + 灵魂拷问 | 强制执行，可验证 |

---

## 三、激进方案：零技能文件架构

### 架构图

```
┌──────────────────────────────────────────────────────────┐
│                     Agent 聚阵层                         │
│  31个Agent JSON — 能力声明 + 触发场景 + 协作伙伴         │
├──────────────────────────────────────────────────────────┤
│                     法则系统层                           │
│  智能体法则 + 质量法则 + 操作法则 — 协作模式 + 门禁       │
├──────────────────────────────────────────────────────────┤
│                     记忆系统层                           │
│  L4 Semantic — 最佳实践 + 失败教训 + 经验复用            │
├──────────────────────────────────────────────────────────┤
│                     MCP 工具层                           │
│  39个MCP协议工具 — 原子能力 + 增强description            │
└──────────────────────────────────────────────────────────┘
```

**变化**：删除技能文件层，其价值分散到4个更底层的机制中。

---

## 四、具体实施方案

### Phase 1: 能力归位（删除前准备）

#### 1.1 MCP工具description增强
- **目标**：每个MCP工具的description字段从一句话扩展为"微型使用说明"
- **内容**：
  - 核心功能一句话
  - 典型触发场景（2-3个）
  - 关键参数说明
  - 常见错误与规避
- **位置**：tool_schema / tool_help 返回的description字段
- **文件**：`mcp_routes_searchperspectivememoriesrequest.py` 中的工具定义

#### 1.2 Agent能力声明强化
- **目标**：Agent JSON文件中的 `capabilities` 字段从标签列表升级为能力声明
- **内容**：
  - 每个能力包含：触发场景 + 主责工具 + 协作工具链
  - 替代技能文件中的"触发场景"和"协作伙伴"
- **文件**：`.trae/agents/_AGENT_REGISTRY.json` + 个体Agent JSON

#### 1.3 L4 Semantic经验库建设
- **目标**：将技能文件中的"最佳实践"、"质量标准"沉淀为记忆经验
- **内容**：
  - 工具使用最佳实践
  - 常见坑与规避方法
  - 组合操作标准流程
- **位置**：ICME L4 Semantic层
- **机制**：每次工具使用后自动评估，优秀实践自动沉淀

### Phase 2: 渐进式删除

#### 2.1 第一批：删除"简单工具"技能（~15个）
- **删除对象**：`list_*`, `get_*`, `stats`, `health` 等自解释工具
- **理由**：工具名 + schema已经完全说明白了
- **验证**：删除后Agent是否还能正确使用这些工具

#### 2.2 第二批：删除"中等工具"技能（~15个）
- **删除对象**：`memory_remember`, `execute_command` 等参数简单的工具
- **理由**：增强后的description + schema足够指导使用
- **验证**：对比删除前后的使用正确率

#### 2.3 第三批：删除"复杂工具"技能（~9个）
- **删除对象**：`agent_dispatch`, `context_extract` 等多步骤工具
- **理由**：操作流程沉淀为L4经验 + Agent能力声明覆盖
- **验证**：全流程测试通过率不下降

### Phase 3: 验证与闭环

#### 3.1 能力不退化验证
- 31个Agent的工具调用正确率不下降
- 6大协作模式正常运转
- Stage Gate通过率不下降

#### 3.2 自进化机制验证
- 新经验能否正确沉淀到L4
- 经验能否被正确检索和复用
- 经验质量是否随时间提升

---

## 五、风险与应对

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| Agent不会用工具了 | 中 | 高 | 增强description + L4经验兜底 |
| 最佳实践丢失 | 低 | 中 | 删除前批量导入L4 Semantic |
| 新人上手变慢 | 中 | 低 | tool_help提供完整使用说明 |
| 调试困难 | 低 | 中 | 经验库支持按工具名搜索 |

---

## 六、预期收益

### 量化收益
| 指标 | 当前 | 目标 |
|------|------|------|
| 技能文件数量 | 39个 | **0个** |
| 需要同步维护的系统数 | 3套（工具+技能+Agent） | **2套（工具+Agent）** |
| 一致性维护成本 | 高 | **零** |
| 最佳实践更新方式 | 手动改文件 | **自动沉淀记忆** |

### 质化收益
1. **单一真相源**：MCP工具 = 能力的唯一权威定义
2. **自进化**：经验通过使用自动积累，不需要人写文档
3. **极简架构**：少一层 = 少一层维护成本 = 少一层不一致风险
4. **符合ICME理念**：知识在记忆中，能力在工具中，调度在Agent中

---

## 七、回滚预案

如果发现能力退化：
1. 从git恢复技能文件（5分钟）
2. 分析哪类工具退化最严重
3. 针对性恢复那部分技能文件
4. 改进替代机制的设计

---

## 八、文件变更清单

### 删除文件（39个技能）
```
.trae/skills/
├── memory-audit/
├── memory-file-capture/
├── memory-recall/
├── memory-remember/
├── memory-smart-dispatch/
├── memory-test/
├── agent-dispatch/
├── agent-transparent-dispatch/
├── auto-memory-capture/
├── context-extract/
├── corpus-batch-import/
├── corpus-extract/
├── corpus-quality-score/
├── corpus-retrieve/
├── data-analyze/
├── dialogue-quality/
├── editor-review/
├── lingjing-14questions/
├── lingjing-9dao-orchestrate/
├── lingjing-dao-compliance/
├── lingjing-memory/
├── lingjing-triple-chain/
├── novel-chapter-create/
├── novel-consistency-check/
├── novel-format-export/
├── novel-multi-schedule/
├── novel-setting-consistency-deep/
├── novel-version-track/
├── novel-worldbuilding-expand/
├── ops-deploy/
├── perf-profile/
├── rule-check/
├── security-audit/
├── skill-route/
├── system-audit/
├── system-diagnose/
├── test-gate/
└── tianji-orchestrate/
```

### 修改文件
- `mcp_routes_searchperspectivememoriesrequest.py` — 增强工具description
- `.trae/agents/_AGENT_REGISTRY.json` — 强化能力声明
- 记忆系统 — 批量导入最佳实践

---

**灵魂拷问**：
- "真的能做到零技能文件吗？" — 需要验证，但方向值得探索
- "删除后能力真的不退化吗？" — 这是整个方案的核心假设，需要Phase 2逐步验证
- "为什么之前没人这么做？" — 因为大多数系统没有ICME六层记忆架构，没有L4经验自进化能力
