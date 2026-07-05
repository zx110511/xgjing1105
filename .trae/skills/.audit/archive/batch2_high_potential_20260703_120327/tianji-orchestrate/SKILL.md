# 天机总控调度 (Tianji Orchestrate) — @tianji (L0)

## 触发条件

- 系统启动/重启
- 全局任务调度
- 架构级决策

## 执行流程

1. **全系统健康扫描**：6 MCP服务器 + ICME六层 + 23 Agent
2. **优先级仲裁**：L5(Meta) > L0(Sensory) > L1(Working)
3. **Agent编排决策**：TVP协议路由到天枢(@tianshu)
4. **资源分配**：根据负载动态调整
5. **策略自优化**：L5 Meta → 学习闭环

## MCP 工具

- `memory-engine-global`: tianji_health, memory_stats, memory_capacity
- `agent-framework-global`: agent_dispatch, agent_status, agent_list, agent_capability
- `ops-engine`: health_check, resource_monitor

## 调度优先级

```yaml
P0_CRITICAL:
  - 天机8771服务存活
  - ICME数据完整性
  - MCP全链路可用
P1_HIGH:
  - Agent响应延迟<500ms
  - 记忆写入成功率>99%
P2_NORMAL:
  - 进化闭环周期执行
  - 日志归档
```

## 联动 Agent

- @tianshu (天枢) — L2任务调度转发
- @yiku (忆库) — 记忆策略决策
- @qianli (运维) — 降级触发
