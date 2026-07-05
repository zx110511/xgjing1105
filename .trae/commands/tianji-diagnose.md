---
name: tianji-diagnose
description: 天机故障诊断 - 快速定位系统异常根因
category: 天机运维
---

# /tianji-diagnose - 天机故障诊断

快速诊断天机v9.1系统异常并给出修复建议。

## 诊断流程
1. 调用 `system_status` 检查MCP全链状态
2. 调用 `tianji_health` 检查ICME六层
3. 检查API端点响应 (http://127.0.0.1:8771/api/health)
4. 收集最近的错误日志
5. 调用 `analyze_bottleneck` 定位性能瓶颈

## 输出
- 故障根因分析
- 影响范围评估
- 修复步骤建议
- 回滚预案

## TVP声明
[TVP]#system→@lingxi→@tianshu | [OPS]#diagnose
