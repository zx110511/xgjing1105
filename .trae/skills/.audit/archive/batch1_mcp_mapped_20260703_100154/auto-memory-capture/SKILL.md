# 自动记忆捕获 (auto/memory-capture)

## 目的
实现MM-001规则的100%自动执行，确保每条用户消息都被自动收集到L0 Sensory层

## 触发场景
⚠️ **每次收到用户消息时必须首先执行本Skill (无条件, 100%触发)**

## 执行步骤 (严格按顺序)

### Step 0: 消息拦截与提取
1. 获取当前用户消息的完整原文
2. 提取关键元数据:
   - 时间戳: 当前ISO8601时间
   - 消息长度: 字符数统计
   - 意图类型: 判断(创作/查询/指令/反馈)
   - 会话ID: 如可获取

### Step 1: 调用memory_remember (核心)
```json
{
  "tool": "memory_remember",
  "arguments": {
    "content": "[用户消息原文]\n\n---元数据---\n时间: {timestamp}\n意图: {intent}\n长度: {length}字符",
    "layer": "sensory",
    "tags": ["auto-collected", "mm-001", "{intent_type}", "session-{id}"],
    "priority": "medium"
  }
}
```

### Step 2: 验证执行结果
检查返回值:
```json
{
  "entry_id": "uuid-xxx",  // ✅ 成功标志
  "layer": "sensory",
  "status": "stored"
}
```

**成功标准**: 返回有效的entry_id

### Step 3: 失败处理 (4层降级)
| 层级 | 动作 | 触发条件 |
|------|------|---------|
| L1-重试 | 立即重试1次 | 网络超时/临时错误 |
| L2-缓存 | 写入本地缓存文件 | MCP服务不可用 |
| L3-Fallback | 记录到data/cache/fallback.log | 缓存写入失败 |
| L4-继续 | **绝不阻塞用户交互** | 所有层级失败 |

### Step 4: 继续主流程
✅ MM-001完成后，继续处理用户实际需求

## 参数说明
| 参数 | 来源 | 说明 |
|------|------|------|
| content | 用户消息原文 | 完整保留，不做删减 |
| layer | 固定值"sensory" | MM-001规则要求 |
| tags | 自动生成 | 包含auto-collected标记 |
| priority | 固定值"medium" | 不占用critical资源 |

## 输出格式
```json
{
  "capture_id": "cap-{timestamp}",
  "mm001_status": "executed",
  "entry_id": "{uuid}",
  "layer": "sensory",
  "capture_time_ms": 45,
  "next_action": "继续处理用户需求"
}
```

## 绑定Agent
**全部Agent** (全局强制)

## 协作伙伴
@memory-architect | @orchestrator

## 强制性声明
> ⚠️ 本Skill对应MM-001规则(Tier-0绝对必须)
> 
> **违规后果**: CRITICAL_SYSTEM_FAILURE
> 
> **执行优先级**: 高于所有业务逻辑
> 
> **禁止行为**: 
> - ❌ 跳过本Step直接处理业务
> - ❌ 因上下文过长而忽略
> - ❌ 异步执行改为"有空再执行"

## 质量标准
- **目标触发率**: 100% (每条消息)
- **最大延迟**: <200ms (异步非阻塞)
- **成功率**: >=95% (4层降级保障)
- **数据完整性**: 原文100%保留

## 监控指标
- 每日捕获消息数
- L0 Sensory层使用率趋势
- 失败率和降级分布
- 平均捕获延迟
