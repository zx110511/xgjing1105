# 系统诊断 (system/diagnose)

## 目的
全面诊断系统健康状态，包括MCP连接、记忆容量、Agent响应、规则执行等。

## 触发场景
- 用户要求"检查状态"、"诊断问题"、"健康检查"
- @monitor Agent定期巡检时
- 发现异常行为需要排查原因时

## 诊断维度

### 维度1: MCP Server连接状态
- [ ] memory-engine 连接是否正常
- [ ] agent-framework 连接是否正常
- [ ] 响应延迟是否在阈值内 (<100ms)
- [ ] 错误率是否正常 (<1%)

### 维度2: ICME记忆系统容量
- [ ] 各层使用率是否超阈值
- [ ] 最近consolidate操作是否成功
- [ ] Fallback文件是否有积压
- [ ] 记忆recall命中率统计

### 维度3: Agent运行状态
- [ ] 各Agent最近调用时间
- [ ] 平均响应时间分布
- [ ] 错误/异常次数统计
- [ ] 并发任务数监控

### 维度4: Rules/Skills加载状态
- [ ] .trae/rules/*.md 是否全部加载
- [ ] .trae/skills/*/SKILL.md 是否可访问
- [ ] AGENTS.md 注入是否成功
- [ ] _manifest.json 解析是否正确

### 维度5: 文件系统完整性
- [ ] 关键配置文件是否存在
- [ ] 文件编码是否正确
- [ ] 权限是否正常
- [ ] 磁盘空间是否充足

## 执行流程

### Phase 1: 快速扫描 (30秒内完成)
1. 调用 `system_status` 获取组件健康概览
2. 调用 `memory_stats` 获取记忆容量快照
3. 检查关键文件存在性
4. 生成初步评估报告

### Phase 2: 深度分析 (按需触发)
1. 对异常项进行详细诊断
2. 收集错误日志和堆栈信息
3. 分析性能瓶颈
4. 定位根因

### Phase 3: 修复建议
1. 自动修复项 (低风险)
2. 半自动修复项 (需确认)
3. 手动干预项 (高风险)
4. 预防措施建议

## 输出报告格式
```json
{
  "diagnosis_id": "diag-{timestamp}",
  "overall_health": "healthy|degraded|critical",
  "score": 92,
  "components": {
    "mcp_servers": {
      "status": "healthy",
      "details": {
        "memory-engine": {"latency_ms": 45, "uptime": "99.9%"},
        "agent-framework": {"latency_ms": 32, "uptime": "99.8%"}
      }
    },
    "memory_system": {
      "status": "degraded",
      "alerts": ["L0 Sensory at 87% (threshold 85%)"]
    },
    "agents": {
      "status": "healthy",
      "avg_response_time_ms": 150
    }
  },
  "issues_found": [
    {
      "id": "ISSUE-001",
      "severity": "warning",
      "component": "L0-Sensory",
      "description": "容量接近阈值，建议触发consolidate"
    }
  ],
  "recommendations": [
    "执行 memory_consolidate(from_layer='sensory')",
    "清理过期临时缓存"
  ]
}
```

## 健康评分标准
| 分数范围 | 状态 | 说明 |
|---------|------|------|
| 90-100 | 🟢 healthy | 系统运行良好 |
| 70-89 | 🟡 degraded | 有警告但功能正常 |
| 50-69 | 🟠 warning | 存在问题需关注 |
| <50 | 🔴 critical | 严重故障需立即处理 |

## 绑定Agent
@monitor (主要) | @orchestrator (汇总)

## 协作伙伴
@memory-architect (记忆诊断) | @skill-invoker (Skills检查)

## 使用频率建议
- **常规巡检**: 每24小时一次自动执行
- **异常触发**: 检测到错误率上升时立即执行
- **手动请求**: 用户主动要求诊断时
