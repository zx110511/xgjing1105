---
name: memory-test
description: "天机v9.1记忆系统专业化测试：使用真实MCP工具调用执行CRUD闭环测试、异常测试、性能基准测试，验证记忆系统功能完整性。"
---

# 记忆系统测试 (Memory Test) — 天机v9.1

## 目的
使用真实MCP工具调用验证天机v9.1 ICME记忆系统的功能完整性、数据一致性和性能表现。作为 Stage Gate SG-3 (MCP集成) 的核心测试组件。

## 触发场景
- 每次 memory-engine-global MCP服务重启后 (健康检查)
- Stage Gate SG-3 门禁流程中 (强制)
- 用户请求"测试记忆系统"
- 记忆系统版本升级后 (回归测试)

## 测试套件

### Test Suite 1: CRUD基础操作

#### TC-1.1: 写入验证 (memory_remember)
```
对六层各写入1条测试数据:
  L0: "测试-L0-{timestamp}" + tags: [test, crud, l0]
  L1: "测试-L1-{timestamp}" + tags: [test, crud, l1]
  L2: "测试-L2-{timestamp}" + tags: [test, crud, l2]
  L3: "测试-L3-{timestamp}" + tags: [test, crud, l3]
  L4: "测试-L4-{timestamp}" + tags: [test, crud, l4]
  L5: "测试-L5-{timestamp}" + tags: [test, crud, l5]

期望: 6/6 返回有效 entry_id
```

#### TC-1.2: 检索验证 (memory_recall)
```
按标签检索: query="测试" + layers=[all] + tags=[test]
期望: 返回≥6条结果, 所有entry_id与写入一致
```

#### TC-1.3: 精确获取 (get_memory)
```
用 entry_id 逐一精确获取
期望: 内容完全匹配写入原文 (逐字比对)
```

#### TC-1.4: 更新验证 (memory_remember + 同entry覆盖)
```
更新 L1 条目: 追加 " - Updated" 到原文
检索验证: 新内容 == 旧内容 + " - Updated"
```

#### TC-1.5: 软删除验证 (memory_forget)
```
软删除 L0 测试条目
检索验证: memory_recall 应不再命中该条目
硬验证: get_memory 返回 deleted=true
```

### Test Suite 2: 跨层操作

#### TC-2.1: 跨层搜索
```
分别按单层和跨层搜索 "测试"
期望: 单层搜索仅返回该层结果, 跨层搜索返回所有层结果
```

#### TC-2.2: 语义搜索 (search_memories)
```
语义搜索: "记忆系统功能验证"
期望: 返回相关结果, 关联度按score排序
```

#### TC-2.3: 记忆血缘 (explain_memory_lineage)
```
查询 L3 测试条目的血缘
期望: 返回创建时间/修改记录/关联条目
```

### Test Suite 3: 异常与边界

#### TC-3.1: 超大内容
```
写入100KB内容到 L3
期望: 返回错误或截断提示 (非崩溃)
```

#### TC-3.2: 空内容
```
写入 content="" 到 L0
期望: 返回参数校验错误
```

#### TC-3.3: 非法layer
```
写入 content="test" layer="invalid_layer"
期望: 返回 layer不支持 错误
```

#### TC-3.4: 重复标签
```
写入相同content两次, 不同tags
期望: 两次都成功, 但去重检测标记为 duplicate
```

#### TC-3.5: 并发写入
```
连续快速写入5条 (不等待返回)
期望: 5/5 成功, 无数据丢失
```

### Test Suite 4: 聚合与统计

#### TC-4.1: 记忆统计 (memory_stats)
```
调用 memory_stats
期望: 返回六层计数/容量/使用率, 所有字段非空
```

#### TC-4.2: 容量查询 (memory_capacity)
```
调用 memory_capacity
期望: 返回各层 capacity/used/percent, 数值递增合理
```

#### TC-4.3: 会话摘要 (get_session_digest)
```
调用 get_session_digest
期望: 返回当前会话的操作摘要
```

### Test Suite 5: 性能基准

#### TC-5.1: 写入延迟
```
连续写入10条, 测量P50/P99延迟
期望: P50 < 100ms, P99 < 500ms
```

#### TC-5.2: 检索延迟
```
query="test", layers=[all], 测量响应时间
期望: P50 < 200ms
```

#### TC-5.3: 批量写入吞吐
```
30秒内持续写入, 统计成功率
期望: ≥95%成功率
```

## 测试数据设计

### 测试标签体系
```
所有测试数据使用统一前缀标签:
  - test (标记为测试数据)
  - test:crud|test:cross|test:edge|test:perf (测试套件)
  - session:test-{timestamp} (测试会话ID)
  - auto-cleanup (标记可自动清理)
```

### 测试数据清理
```
测试完成后:
1. memory_forget 所有 test 标签条目 (软删除)
2. 验证清理完整性: memory_recall test → 返回0条
3. 如清理失败, 保留标记供下次审计自动清理
```

## MCP工具链

| 工具 | 测试套件 | 调用次数(估计) |
|------|----------|---------------|
| memory_remember | TC-1.1/1.4/3.1-3.5 | ~20 |
| memory_recall | TC-1.2/2.1/5.2 | ~15 |
| get_memory | TC-1.3/1.5 | ~10 |
| memory_forget | TC-1.5/清理 | ~8 |
| search_memories | TC-2.2 | ~3 |
| explain_memory_lineage | TC-2.3 | ~2 |
| memory_stats | TC-4.1 | ~3 |
| memory_capacity | TC-4.2 | ~2 |
| get_session_digest | TC-4.3 | ~1 |

## 输出报告格式
```json
{
  "test_id": "mt-{timestamp}",
  "test_duration_ms": 4500,
  "summary": {
    "total": 20,
    "passed": 19,
    "failed": 1,
    "skipped": 0,
    "pass_rate": 0.95
  },
  "suites": {
    "crud_basic": {"total": 5, "passed": 5, "failed": 0},
    "cross_layer": {"total": 3, "passed": 3, "failed": 0},
    "edge_cases": {"total": 5, "passed": 5, "failed": 0},
    "aggregation": {"total": 3, "passed": 3, "failed": 0},
    "performance": {"total": 4, "passed": 3, "failed": 1}
  },
  "failures": [
    {
      "tc_id": "TC-5.1",
      "reason": "P99延迟 620ms 超阈值 500ms",
      "severity": "minor"
    }
  ],
  "performance_baseline": {
    "write_p50_ms": 45,
    "write_p99_ms": 380,
    "recall_p50_ms": 85,
    "throughput_30s": 142
  },
  "verdict": "PASS|BLOCK",
  "stage_gate": "SG-3 MCP Integration"
}
```

## 通过标准

| 测试套件 | 最低通过率 | 阻断条件 |
|----------|-----------|---------|
| CRUD基础 | 100% | 任何失败 → BLOCK |
| 跨层操作 | 100% | 任何失败 → BLOCK |
| 异常边界 | 100% | 崩溃 → BLOCK |
| 聚合统计 | 100% | 数据异常 → BLOCK |
| 性能基准 | 90% | P99 > 2s → BLOCK |

## 绑定Agent
@tiewei (主要, 测试门禁) | @yiku (辅助, 记忆验证)

## 协作伙伴
@zhuiguang (性能基准) | @qianli (MCP可用性)

## Stage Gate 集成
- **SG-3 (MCP集成)**: memory-test 是必过项
- 测试失败 → SG-3 BLOCK → 必须修复后重新提交
- 性能退化 >10% → 记录到 L5 Meta + 通知 @zhuiguang

## 测试数据管理
- 所有测试数据使用 `test` 标签
- 测试完成后自动清理 (Soft Delete)
- 清理失败条目在下次 memory-audit 中标记为 orphan
- 测试结果写入 L3 Episodic (永久保留)

---

**版本**: 1.0.0 | **体系**: 天机v9.1 | **维护**: @tiewei + @yiku
