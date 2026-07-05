---
name: lingjing-dao-compliance
description: "灵境代码变更; 架构提案; 天机修复法则升级"
---

# 道谱合规 (Dao Spectrum Compliance) — 灵境·证

## 触发条件
- 灵境代码变更
- 架构提案
- 天机修复法则升级

## 执行流程
1. **九道校验**：
   - 道一·始道 — 核心原则锚定
   - 道二·生道 — 双链验证打通
   - 道三·化道 — 三维透视完备
   - 道四·成道 — 持续进化闭环
   - 道五·正道 — 纠偏恢复机制
   - 道六·合道 — 跨系统融合
   - 道七·传道 — 知识传递完整性
   - 道八·护道 — 安全防御体系
   - 道九·明道 — 可观测性全链路
2. **三十六地煞检查**：每个地煞点逐一核对
3. **七十二天罡验证**：每个天罡点逐一核对
4. **合规报告**：生成道谱合规矩阵

## MCP 工具
- `security-scanner`: scan_vulnerabilities, check_compliance, get_security_report
- `agent-framework-global`: rule_evaluate, system_status
- `knowledge-graph-global`: kg_query, kg_validate

## 合规等级
```yaml
九道:
  始道: HARD_BLOCK # 核心原则必须满足
  生道: HARD_BLOCK # 双链必须打通
  化道: SOFT_WARN  # 三维可以有缺失
  成道: INFO       # 进化可以持续
  正道: SOFT_WARN  # 纠偏机制建议有
  合道: SOFT_WARN  # 跨系统融合建议
  传道: INFO       # 知识传递非必须
  护道: HARD_BLOCK # 安全防御必须
  明道: SOFT_WARN  # 可观测性建议

地煞(36): 逐项检查，缺失>5 → BLOCK
天罡(72): 逐项检查，缺失>10 → WARN
```

## 联动 Agent
- @luling (律令) — 天机规则对接
- @zhenshan (镇山) — 安全合规协同
