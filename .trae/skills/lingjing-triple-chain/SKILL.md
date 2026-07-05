---
name: lingjing-triple-chain
description: "代码变更后; 架构决策; 发布前检查"
---

# 三链协调验证 (Triple Chain Coordination) — 灵境·枢

## 触发条件
- 代码变更后
- 架构决策
- 发布前检查

## 三链定义
```
体验链 (Experience Chain) → 用户感知层
  ├─ 用户交互流畅度
  ├─ 响应延迟感知
  ├─ 信息可发现性
  └─ 错误恢复体验

业务链 (Business Chain) → 逻辑核心层
  ├─ 业务流程完整性
  ├─ 规则一致性
  ├─ 数据一致性
  └─ 异常处理完备性

技术链 (Technical Chain) → 基础设施层
  ├─ ICME记忆层状态
  ├─ MCP服务器健康
  ├─ Agent调度延迟
  └─ 进化闭环健康
```

## 执行流程
1. **三链建模**：从代码变更中提取三链模型
2. **链内一致性**：每条链内部节点的一致性验证
3. **链间协调性**：链与链之间的协调关系验证
4. **冲突检测**：标识三链间的冲突
5. **协调建议**：给出三链协调修正建议

## MCP 工具
- `agent-framework-global`: agent_dispatch, system_status, context_extract
- `memory-engine-global`: memory_recall, get_session_digest
- `ops-engine`: get_resource_usage, list_services

## 输出格式
```yaml
chain_status:
  experience: {score: 0.85, violations: 2}
  business:   {score: 0.92, violations: 0}
  technical:  {score: 0.78, violations: 3}
cross_chain_conflicts: 1
verdict: PASS_WITH_WARNINGS
```
