---
name: lingjing-9dao-orchestrate
description: "灵境任务调度; 道谱变更; 系统启动"
---

# 灵境九道编排 (LingJing 9-Dao Orchestration) — 灵境·枢

## 触发条件
- 灵境任务调度
- 道谱变更
- 系统启动

## 九道调度图
```
始道(道一) → 核心原则锚定 ← @luling 规则守护
  ↓
生道(道二) → 双链验证打通 ← @tianshu 天枢调度
  ↓
化道(道三) → 三维透视完备 ← @dongcha 洞察分析
  ↓
成道(道四) → 持续进化闭环 ← @huasheng 化生进化
  ↓
正道(道五) → 纠偏恢复    ← @tiewei 铁卫守护
  ↓
合道(道六) → 跨系统融合   ← @tianji 天机总控
  ↓
传道(道七) → 知识传递     ← @mingjing 明镜审校
  ↓
护道(道八) → 安全防御     ← @zhenshan 镇山守护
  ↓
明道(道九) → 可观测性     ← @qianli 千里监控
```

## 执行流程
1. **道谱状态扫描**：检查每道的健康状态
2. **依赖解析**：按九道依赖关系编排
3. **Agent分配**：每道分配对应Agent
4. **并行优化**：无依赖的道可并行
5. **闭环反馈**：成道(道四)收集反馈驱动进化

## MCP 工具
- `agent-framework-global`: agent_dispatch, agent_status, agent_list, agent_capability
- `memory-engine-global`: tianji_health, memory_stats
- `ops-engine`: health_check, resource_monitor

## 道谱状态模板
```yaml
九道状态:
  始道: {status: HEALTHY, last_check: "..."}
  生道: {status: HEALTHY, last_check: "..."}
  化道: {status: DEGRADED, issue: "三维透视缺失体验维"}
  成道: {status: EVOLVING, cycles: 42}
  正道: {status: HEALTHY}
  合道: {status: PENDING, depends: "天机8771"}
  传道: {status: HEALTHY}
  护道: {status: HEALTHY}
  明道: {status: WARNING, issue: "L5元认知指标掉线"}
```
