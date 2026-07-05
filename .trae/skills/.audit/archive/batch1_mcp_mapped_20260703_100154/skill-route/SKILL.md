# 技能路由 (Skill Route) — @baiqiao (L1)

## 触发条件

- 用户发出指令/提问
- 系统内部跨Agent请求
- Skill调用链编排

## 执行流程

1. **意图解析**：分析用户输入/系统请求
2. **能力映射**：查询 agent-framework → agent_capability
3. **Skill匹配**：根据意图匹配最佳Skill
4. **路由决策**：单一Agent直调 or 多Agent串联
5. **回退策略**：无匹配时 → 降级到@lingxi(通用对话)

## MCP 工具

- `agent-framework-global`: agent_capability, agent_dispatch, agent_list
- `memory-engine-global`: memory_query, memory_search
- `knowledge-graph-global`: kg_query

## 路由规则

```yaml
route_matrix:
  code_task:      [@jingwei→@wenzong→@gongzao]
  security_scan:  [@zhenshan→@luling]
  test_run:       [@tiewei→@zhuiguang]
  deploy:         [@gongzao→@qianli]
  memory_query:   [@yiku→@mingjing]
  general_chat:   [@lingxi]
  agent_create:   [@kuangshi→@gongzao]
  evolution:      [@evolver→@yiku]
```

## 联动 Agent

- @tianshu (天枢) — L2任务调度转发
- @lingxi (对话) — 回退通用对话
- @mingjing (记忆检索) — Skill历史上下文
