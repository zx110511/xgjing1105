# 记忆存储 (memory/remember)

## 目的
将内容存储到ICME六层记忆系统的指定层级。

## 触发场景
- 每次收到用户消息时 (MT-002强制规则)
- Agent完成创作/分析后需要保存结果时
- 用户明确要求"记住这个"、"存到记忆"时

## 执行步骤

### Step 1: 参数准备
1. **content** (必需): 要存储的内容文本
   - 完整原文，不做截断或修改
2. **layer** (推荐): 目标记忆层
   - `sensory` - 原始输入(L0)
   - `working` - 当前会话上下文(L1)
   - `short_term` - 跨会话短期信息(L2)
   - `episodic` - 事件经历/创作记录(L3)
   - `semantic` - 知识概念/世界观设定(L4)
   - `meta` - 系统策略/架构决策(L5)
3. **tags** (推荐): 标签列表便于检索
   - 格式: `category:subcategory:value`
   - 示例: `novel:chapter:15`, `character:林远`

### Step 2: 调用MCP工具
```
工具: memory_remember
参数:
{
  "content": "{prepared_content}",
  "layer": "{target_layer}",
  "tags": ["{tag1}", "{tag2}"],
  "priority": "low|medium|high|critical"
}
```

### Step 3: 验证结果
1. 检查返回的 `entry_id` 是否有效
2. 记录存储位置和层信息
3. 失败时执行降级策略

## 错误处理 (4层降级)
1. **重试**: 指数退避 (1s, 2s, 4s) 最多3次
2. **本地缓存**: 进程级字典临时存储
3. **Fallback文件**: 写入 `data/cache/memory_fallback/`
4. **继续主流程**: **绝对不阻塞用户交互!**

## 存储约定参考
| 内容类型 | 推荐Layer | 标签示例 | 大小限制 |
|---------|----------|---------|---------|
| 用户原始输入 | sensory | auto-collected, msg-type:* | <1KB |
| 当前会话变量 | working | session:{id}, active | <10MB |
| 创作章节 | episodic | novel:chapter:{n} | <200MB |
| 世界观设定 | semantic | worldbuilding:* | <500MB |
| 架构决策 | meta | decision:project:* | <100MB |

## 绑定Agent
@memory-architect (主要) | @writer | @reviewer | @planner | @analyzer (均可调用)

## 强制规则关联
- **MM-001**: 每次消息自动收集到L0 Sensory
- **MT-002**: 与输入适配流水线同步触发
