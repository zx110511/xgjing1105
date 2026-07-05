---
name: lingjing-14questions
description: "新功能开发启动; 架构变更提案; 代码审查"
---

# 拷问驱动开发 (14-Question Driven Dev) — 灵境·质

## 触发条件
- 新功能开发启动
- 架构变更提案
- 代码审查

## 十四拷问流程
1. **灵境拷问 (前7问·设计阶段)**：
   - Q1: 此功能对应道谱哪一道？
   - Q2: 涉及哪些地煞点？需要新增吗？
   - Q3: 触发哪些天罡点？需要调整吗？
   - Q4: 三链（体验→业务→技术）影响分析？
   - Q5: 是否需要新地煞定义？
   - Q6: 是否需要新天罡定义？
   - Q7: 九道完整性是否受影响？

2. **天机拷问 (后7问·实现阶段)**：
   - Q8: ICME六层记忆影响？
   - Q9: TVP透明调度链路是否完整？
   - Q10: Agent能力矩阵是否需要更新？
   - Q11: Skill映射是否需要新增？
   - Q12: MCP工具是否需要新增？
   - Q13: 天机修复法则是否被违反？
   - Q14: 进化闭环是否需要调整？

## MCP 工具
- `agent-framework-global`: rule_evaluate, system_status, context_extract
- `memory-engine-global`: memory_recall, search_memories
- `knowledge-graph-global`: kg_query, kg_validate

## 输出格式
```json
{
  "feature": "新功能描述",
  "lingjing_questions": [{"Q":"Q1","answer":"...","pass":true},...],
  "tianji_questions": [{"Q":"Q8","answer":"...","pass":true},...],
  "verdict": "PASS|REVISE|BLOCK",
  "missing_elements": [],
  "suggestions": []
}
```
