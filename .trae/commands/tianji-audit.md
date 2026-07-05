---
name: tianji-audit
description: 天机系统科学审计 (系统/代码/记忆三合一)
category: 天机运维
---

# /tianji-audit - 天机科学审计

执行天机v9.1系统全量科学审计。

## 审计维度
1. **系统健康**: API/ICME/MCP/Agent/DeepSeek 五链健康
2. **代码审计**: 调用 `rule_evaluate` 检查天机宪法合规
3. **记忆审计**: 调用 `memory-audit` skill 检查六层一致性
4. **安全扫描**: 调用 `scan_vulnerabilities` + `check_compliance`
5. **性能剖析**: 调用 `get_performance_metrics` + `analyze_bottleneck`
6. **Skills完整性**: 检查50+ skills注册和可用性
7. **Commands完整性**: 检查所有命令配置

## 输出
生成 `审计报告_YYYY-MM-DD.md` 写入 `.trae/skills/.audit/`

## TVP声明
[TVP]#system→@mingjing→@tianshu | [OPS]#full_audit
