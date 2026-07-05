---
name: lingjing-memory
description: "灵境任务执行后; 道谱状态变更; 三链协调分析后"
---

# 灵境记忆系统 (LingJing Memory System) — 灵境·识

## 触发条件
- 灵境任务执行后
- 道谱状态变更
- 三链协调分析后

## 灵境记忆分层 (ICME扩展)
```
灵境L6 — 道谱记忆 (Dao Spectrum Memory)
  ├─ 九道当前状态快照
  ├─ 三十六地煞检查清单历史
  ├─ 七十二天罡验证记录
  └─ 道谱演化路径

灵境L5 — 元认知记忆 (共享天机L5)
  ├─ 道谱进化策略
  ├─ 三链协调学习模式
  └─ 拷问驱动经验积累

灵境L4 — 模式记忆 (共享天机L4)
  ├─ 道谱合规模式
  ├─ 三链冲突模式
  └─ 拷问通过/失败模式
```

## 执行流程
1. **道谱快照**：定期保存九道状态
2. **地煞/天罡追踪**：每次检查后记录结果
3. **三链历史**：保存三链协调分析结果
4. **进化学习**：L5元认知分析优化策略

## MCP 工具
- `memory-engine-global`: memory_remember, memory_recall, memory_stats, memory_consolidate, build_working_representation, run_reflective_cycle
- `knowledge-graph-global`: kg_query

## 绑定Agent
@lianli (知识图谱) | @yiku (记忆中枢)

## 记忆数据结构
```json
{
  "dao_spectrum_snapshot": {
    "timestamp": "...",
    "nine_dao_status": {},
    "disha_checks": 36,
    "tiangang_checks": 72
  },
  "triple_chain_history": {
    "last_check": "...",
    "experience_score": 0.85,
    "business_score": 0.92,
    "technical_score": 0.78
  },
  "14_questions_log": {
    "total_executions": 150,
    "pass_rate": 0.87,
    "common_failures": ["Q4","Q11"]
  }
}
```
