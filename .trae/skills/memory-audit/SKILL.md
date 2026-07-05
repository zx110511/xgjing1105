---
name: memory-audit
description: "天机v9.1深度记忆审计：CRUD闭环验证、跨层一致性检查、容量趋势分析、质量评分、孤儿记忆发现。"
---

# 记忆系统审计 (Memory Audit) — 天机v9.1

## 目的
对天机v9.1 ICME六层记忆系统进行深度审计，超越 system-audit 的模块级扫描，深入到记忆数据的完整性、一致性和质量层面。

## 触发场景
- 用户请求"审计记忆"、"检查记忆一致性"
- 每次 memory_consolidate 整合操作后 (自动触发)
- 每日定时巡检 (配合 system-diagnose)
- 发现数据异常后根因追溯

## 审计维度

### 维度1: CRUD闭环验证
```
写入验证:
  写入 N 条测试数据 → memory_recall 检索 → 比对原文一致性
  ├─ 内容完整性: 写入内容 == 检索内容 (逐字比对)
  ├─ 标签完整性: 写入标签 == 检索标签
  ├─ 层级正确性: 写入layer == 检索layer
  └─ 时间戳有效性: 写入时间 <= 检索时间 (单调性)

更新验证:
  更新条目 → 检索旧版本 → 检索新版本 → 比对差异

删除验证:
  软删除条目 → memory_recall 应不再命中
```

### 维度2: 跨层一致性检查
```
跨层引用完整性:
  ├─ L3→L1: 文件记录的parent_message_id对应L1中存在
  ├─ L4→L3: 知识引用的源文件记录存在
  ├─ L5→L4: 策略引用的架构决策记录存在
  └─ 反向: L0→L3 的消息→文件追溯链完整

数据矛盾检测:
  ├─ 同标签不同层出现冲突内容
  ├─ 同名文件不同hash无版本关联
  └─ 时间戳倒序 (后写入的timestamp早于先写入)
```

### 维度3: 容量趋势分析
调用 `memory_stats` + `memory_capacity`:
```
六层使用率:
  L0 Sensory: {used}/{capacity} ({percent}%)
  L1 Working: {used}/{capacity} ({percent}%)
  L2 Short-Term: {used}/{capacity} ({percent}%)
  L3 Episodic: {used}/{capacity} ({percent}%)
  L4 Semantic: {used}/{capacity} ({percent}%)
  L5 Meta: {used}/{capacity} ({percent}%)

增长预测:
  基于最近7天趋势 → 预测何时达到阈值
  超标告警: 使用率 > 85%
```

### 维度4: 质量评分

| 质量指标 | 计算方式 | 目标 |
|----------|----------|------|
| 标签覆盖率 | tagged_entries / total_entries | ≥95% |
| 重复率 | duplicate_entries / total_entries | <5% |
| 孤儿率 | orphan_entries / total_entries | <1% |
| 过期率 | expired_entries / total_entries | <10% |
| 空值率 | empty_content / total_entries | 0% |

### 维度5: 审计合规
- 检查写入操作是否都有 operation_header
- 检查异常是否都记录到 L3 Episodic
- 检查 L4/L5 写入是否有二次确认
- 检查软删除是否遵循 retain_forever 策略

## 执行流程

### Phase 1: 快速扫描 (<30s)
1. memory_stats → 六层容量快照
2. memory_capacity → 使用率/阈值
3. 抽样检查(每层随机10条) → 格式完整性
4. 生成初步评分

### Phase 2: 深度审计 (按需, <5min)
1. CRUD闭环测试(每层2条)
2. 跨层引用完整性扫描
3. 矛盾/孤儿/重复检测
4. 合规性检查

### Phase 3: 修复建议
1. 自动修复: 标签补全 / 孤儿关联 / 过期清理
2. 半自动: 矛盾确认 / 版本合并
3. 手动: 策略调整 / 架构决策修正

## MCP工具链

| 工具 | 用途 | 调用时机 |
|------|------|---------|
| memory_stats | 六层统计 | Phase 1 |
| memory_capacity | 容量监控 | Phase 1 |
| memory_recall | 抽样检索+闭环验证 | Phase 1+2 |
| search_memories | 语义搜索 | Phase 2 |
| get_memory | 精确获取 | Phase 2 |
| list_memories | 批量列表 | Phase 2 |
| memory_forget | 过期清理 | Phase 3 |
| explain_memory_lineage | 血缘追溯 | Phase 2 |

## 输出报告格式
```json
{
  "audit_id": "ma-{timestamp}",
  "audit_type": "quick|deep",
  "overall_score": 92,
  "grade": "A|B|C|D|F",
  "dimensions": {
    "crud_integrity": {"score": 98, "issues": 0},
    "cross_layer_consistency": {"score": 85, "issues": 3},
    "capacity_health": {"score": 90, "warnings": ["L0 at 87%"]},
    "quality_metrics": {
      "tag_coverage": 0.96,
      "duplicate_rate": 0.03,
      "orphan_rate": 0.01,
      "expiry_rate": 0.05,
      "empty_rate": 0.0
    },
    "compliance": {"score": 95, "violations": 1}
  },
  "issues": [
    {
      "id": "AUDIT-001",
      "severity": "warning",
      "dimension": "cross_layer",
      "description": "L3 entry-xxx引用的L1 parent不存在"
    }
  ],
  "recommendations": [
    "执行 memory_consolidate(L0→L1) 释放Sensory空间",
    "清理15条过期L2条目",
    "修复3处跨层引用断裂"
  ]
}
```

## 健康等级
| 分数 | 等级 | 含义 |
|------|------|------|
| 95-100 | A | 记忆系统健康, 数据完整 |
| 85-94 | B | 有轻微问题, 建议修复 |
| 70-84 | C | 存在需关注问题 |
| 50-69 | D | 数据完整性受损 |
| <50 | F | 严重故障, 需立即处理 |

## 绑定Agent
@yiku (主要) | @mingjing (质量审校)

## 协作伙伴
@tiansuan (趋势分析) | @qianli (容量告警)

## 执行频率
- 快速扫描: 每24小时自动
- 深度审计: 每周一次 / consolidate后
- 手动触发: 用户请求 / 异常发生后

---

**版本**: 1.0.0 | **体系**: 天机v9.1 | **维护**: @yiku + @mingjing
