# 一致性检查 (novel/consistency-check)

## 目的
检查小说内容的内部一致性，包括设定冲突、人物行为逻辑、时间线错误等。

## 触发场景
- 用户要求"检查一致性"、"校验错误"、"审校"
- @reviewer Agent执行质量审校任务时
- 创作完成后进入审校阶段时

## 执行步骤

### Step 1: 加载基线数据
1. 调用 `memory_recall` 查询:
   - 世界观设定基线
   - 人物角色卡(所有出场人物)
   - 力量体系规则
   - 前文章节摘要
   - 版本追踪记录

### Step 2: 多维度检查

#### 2.1 世界观一致性
- [ ] 力量体系使用是否符合规则
- [ ] 设定元素是否前后矛盾
- [ ] 科技/魔法水平是否统一
- [ ] 社会/政治结构是否一致

#### 2.2 人物一致性
- [ ] 人物性格是否符合角色卡
- [ ] 行为动机是否合理
- [ ] 能力范围是否超出设定
- [ ] 人际关系是否连贯
- [ ] 成长轨迹是否自然

#### 2.3 时间线一致性
- [ ] 时间顺序是否正确
- [ ] 事件因果关系是否合理
- [ ] 年龄/时间跨度是否准确
- [ ] 季节/天气是否连续

#### 2.4 文字一致性
- [ ] 人物称呼是否统一
- [ ] 地名/物品名拼写一致
- [ ] 数值/数据前后吻合
- [ ] 标点符号规范使用

### Step 3: 问题分级报告
```json
{
  "check_id": "cc-{timestamp}",
  "scope": "{chapter_range}",
  "summary": {
    "total_issues": N,
    "critical": 0,
    "major": 2,
    "minor": 5,
    "suggestion": 3
  },
  "issues": [
    {
      "id": "ISSUE-001",
      "severity": "major",
      "category": "worldbuilding",
      "location": "第15章 第3段",
      "description": "力量体系使用不符合设定",
      "baseline_ref": "规则v2.0-第3条",
      "suggestion": "修改为符合L3级能力描述"
    }
  ],
  "pass_rate": 0.85
}
```

## 参数说明
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| target_chapters | array | ✅ | - | 待检查的章节列表 |
| check_depth | enum | ❌ | standard | quick/standard/deep |
| baseline_version | string | ❌ | latest | 设定基线版本 |

## 输出格式
- JSON结构化报告 (详细版)
- Markdown摘要 (快速版)

## 严重度定义
| 级别 | 定义 | 示例 |
|------|------|------|
| 🔴 critical | 导致剧情无法自洽 | 主角死亡后又出现 |
| 🟠 major | 明显矛盾需修正 | 能力突然提升无解释 |
| 🟡 minor | 小瑕疵可后续处理 | 称呼不统一 |
| 🔵 suggestion | 优化建议非错误 | 表达可更精炼 |

## 绑定Agent
@reviewer (主要) | @version-keeper (版本对比)

## 协作伙伴
@writer (接收修改建议) | @planner (设定咨询) | @memory-architect (基线查询)

## 质量标准
- **通过标准**: critical=0, major≤2, pass_rate≥90%
- **优秀标准**: critical=0, major=0, pass_rate≥95%
- **不通过**: 需返回@writer修改后重新提交
