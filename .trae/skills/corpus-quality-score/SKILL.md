# 语料质量评分 (corpus/quality-score)

## 目的
对语料库中的条目进行多维度质量评分，支持批量评分、趋势分析和低质量标记

## 触发场景
- 导入新语料后需要评估质量
- 定期语料库健康检查
- 识别需清理的低质量条目
- 分析语料质量分布趋势

## 执行步骤
### Step 1: 确定评分范围
1. 解析target参数(all/by_source/by_dimension/by_tag)
2. 确定待评分条目集合
3. 加载维度配置(dimensions)

### Step 2: 多维度评分
#### 2.1 完整性 (completeness)
- [ ] 必填字段是否完整
- [ ] 内容长度是否达标
- [ ] 元数据是否齐全

#### 2.2 准确性 (accuracy)
- [ ] 内容是否符合类别定义
- [ ] 标签是否正确
- [ ] 引用是否有效

#### 2.3 独特性 (uniqueness)
- [ ] 与其他条目重复率
- [ ] 信息增量价值
- [ ] 原创性评估

#### 2.4 可用性 (usability)
- [ ] 格式规范程度
- [ ] 可读性评分
- [ ] 集成便利性

#### 2.5 多样性 (diversity)
- [ ] 类型分布均衡性
- [ ] 风格覆盖广度
- [ ] 来源多样性

### Step 3: 生成报告
1. 计算综合得分(加权平均)
2. 标记低于min_score的条目
3. 生成趋势分析图表数据
4. 输出改进建议

## 参数说明
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| target | string | ❌ | all | 评分范围: all/by_source/by_dimension/by_tag |
| dimensions | array | ❌ | 全部5维 | 评分维度列表 |
| min_score | number | ❌ | 0.0 | 最低评分阈值 |
| generate_report | boolean | ❌ | true | 是否生成详细报告 |

## 输出格式
```json
{
  "score_id": "qs-{timestamp}",
  "scope": "{target}",
  "summary": {
    "total_items": N,
    "avg_score": 0.75,
    "high_quality": N,  // >=0.8
    "medium_quality": N, // 0.5-0.8
    "low_quality": N     // <0.5 (需清理)
  },
  "dimension_scores": {
    "completeness": 0.82,
    "accuracy": 0.78,
    "uniqueness": 0.71,
    "usability": 0.76,
    "diversity": 0.68
  },
  "low_quality_items": [
    {
      "id": "corp-{id}",
      "score": 0.35,
      "issues": ["字段缺失", "内容过短"]
    }
  ],
  "trends": {
    "vs_last_week": "+0.05",
    "quality_direction": "improving"
  },
  "recommendations": [
    "建议清理15个低质量条目",
    "补充emotion类语料(当前仅占8%)"
  ]
}
```

## 绑定Agent
@corpus-miner

## 协作伙伴
@analyzer | @writer

## 质量标准
- 评分覆盖率达到100%
- 维度权重配置合理
- 报告生成时间 < 30s
