---
name: tianji-health
description: 天机v9.1系统全链健康检查
category: 天机运维
---

# /tianji-health - 天机全链健康检查

执行天机v9.1全系统健康诊断：

## 检查清单
1. **API健康**: GET http://127.0.0.1:8771/api/health
2. **ICME六层记忆**: 调用 `tianji_health` MCP工具
3. **容器模块**: 验证15/15模块在线
4. **MCP全链**: 6个MCP server状态验证 (`system_status`)
5. **Agent调度**: 验证24 Agent在线 (`tianji_amim_status`)
6. **记忆统计**: 调用 `memory_stats` 检查容量和命中率
7. **DeepSeek大脑**: 验证LLM驱动状态

## 输出格式
生成结构化健康报告，包含：
- 健康指示灯 (🟢/🟡/🔴)
- ICME六层容量使用率
- 模块在线率
- MCP工具可用率
- 建议修复项

## TVP声明
[TVP]#system→@lingxi→@tianshu | [OPS]#health_check
