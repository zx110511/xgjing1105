# 🎭 元初系统智能体命名体系 v4.2 扩展版（含Trae官方与内置Agent）

## 📋 标准命名表（方案A — 中文主名）

所有Agent遵循**统一命名标准**：2字中文名 + 拼音英文ID

### L0 — 系统根基层 (2个)

| # | 中文名 | 英文ID | 角色 | 含义 | MCP主服务器 |
|---|--------|--------|------|------|------------|
| 0 | 天机 | `tianji` | 系统总控 | 天机不可泄露，系统最高机枢 | agent-framework-global |
| 1 | 铁卫 | `tiewei` | 质量守护 | 铜墙铁壁，质量守门 | security-scanner |

### L1 — 感知基础层 (5个)

| # | 中文名 | 英文ID | 角色 | 含义 | MCP主服务器 |
|---|--------|--------|------|------|------------|
| 2 | 忆库 | `yiku` | 记忆架构 | 记忆库房，知识管理 | memory-engine-global |
| 3 | 洞察 | `dongcha` | 上下文分析 | 洞察入微，意图识别 | agent-framework-global |
| 4 | 律令 | `luling` | 规则守护 | 律法命令，规则执行 | agent-framework-global |
| 5 | 灵犀 | `lingxi` | 会话监控 | 心有灵犀，上下文保护 | agent-framework-global |
| 6 | 万象 | `wanxiang` | 多模态感知 | 万象森罗，全模态感知 | memory-engine-global |

### L2 — 业务核心层 (8个)

| # | 中文名 | 英文ID | 角色 | 含义 | MCP主服务器 |
|---|--------|--------|------|------|------------|
| 7 | 天枢 | `tianshu` | 总指挥 | 北斗第一星，中枢之枢 | agent-framework-global |
| 8 | 文宗 | `wenzong` | 主编 | 文坛宗师，统领全局 | agent-framework-global |
| 9 | 经纬 | `jingwei` | 架构师 | 经天纬地，规划宏图 | agent-framework-global |
| 10 | 妙笔 | `miaobi` | 创作者 | 妙笔生花，内容创作 | memory-engine-global |
| 11 | 明镜 | `mingjing` | 审校者 | 明镜高悬，明察秋毫 | agent-framework-global |
| 12 | 天算 | `tiansuan` | 数据分析 | 天算神机，数据分析 | memory-engine-global |
| 13 | 矿师 | `kuangshi` | 语料处理 | 开矿大师，原料供给 | memory-engine-global |
| 14 | 连理 | `lianli` | 知识图谱 | 连理之木，知识互联 | memory-engine-global |

### L3 — 工程执行层 (4个)

| # | 中文名 | 英文ID | 角色 | 含义 | MCP主服务器 |
|---|--------|--------|------|------|------------|
| 15 | 百巧 | `baiqiao` | 技能代理 | 百巧百能，技能大全 | command-executor |
| 16 | 史官 | `shiguan` | 版本追踪 | 史官记录，版本追踪 | memory-engine-global |
| 17 | 锦书 | `jinshu` | 成品导出 | 锦书寄情，成品美化 | command-executor |
| 18 | 化生 | `huasheng` | 进化工程 | 化生万物，持续演进 | memory-engine-global |

### L4 — 运维保障层 (4个)

| # | 中文名 | 英文ID | 角色 | 含义 | MCP主服务器 |
|---|--------|--------|------|------|------------|
| 19 | 千里 | `qianli` | 系统监控 | 千里之眼，系统监控 | performance-profiler |
| 20 | 工造 | `gongzao` | DevOps | 工部制造，运维工程 | ops-engine |
| 21 | 镇山 | `zhenshan` | 安全审计 | 镇山之宝，安全守护 | security-scanner |
| 22 | 追光 | `zhuiguang` | 性能优化 | 追光逐电，极致性能 | performance-profiler |

### 附加 — 轻量辅助 (1个)

| # | 中文名 | 英文ID | 角色 | 含义 | MCP主服务器 |
|---|--------|--------|------|------|------------|
| 23 | 简衡 | `jianheng` | 轻量评估 | 简明衡断，快速评估 | agent-framework-global |

### Trae官方系列 (7个)

| # | 中文名 | 英文ID | 角色 | 来源 |
|---|--------|--------|------|------|
| 24 | UI设计师 | `ui-designer` | 界面设计师 | trae-official |
| 25 | 前端架构师 | `frontend-architect` | 前端架构师 | trae-official |
| 26 | 后端架构师 | `backend-architect` | 后端架构师 | trae-official |
| 27 | API测试专家 | `api-test-pro` | API测试专家 | trae-official |
| 28 | AI集成工程师 | `ai-integration-engineer` | AI集成工程师 | trae-official |
| 29 | 性能优化专家 | `performance-expert` | 性能优化专家 | trae-official |
| 30 | 合规检查专家 | `compliance-checker` | 合规检查专家 | trae-official |

### Trae内置智能体 (2个)

| # | 中文名 | 英文ID | 角色 | 来源 |
|---|--------|--------|------|------|
| 31 | 对话 | `trae-chat` | Trae内置对话入口 | trae-builtin |
| 32 | 智能体 | `trae-agent` | Trae内置智能体入口 | trae-builtin |

## 🔧 命名规范

```
界面显示: 天枢
程序调用: @tianshu
英文标识: tianshu-orchestrator (Trae面板)
文档引用: 天枢(@tianshu)
```

**Trae官方系列命名规则**：
- 程序调用: `@{english-id}`（如 `@ui-designer`）
- 文档引用: `UI设计师(@ui-designer)`
- 文件命名: `trae-official-{english-id}.json`

**Trae内置智能体命名规则**：
- 程序调用: `@trae-chat`、`@trae-agent`
- 界面显示: 保留原Trae名称（Chat、Agent）
- 内部标识: `builtin:` 前缀（如 `builtin:trae-chat`）

## 📁 文件命名标准

```
天机系列Agent定义文件:   .trae/agents/tianji-{agent_id}.json         (如 tianji-tianshu.json)
Trae面板配置文件:         .trae/agents/trae-official-{agent_id}.json   (如 trae-official-tianshu.json)
Trae官方Agent定义文件:    .trae/agents/trae-official-{english-id}.json (如 trae-official-ui-designer.json)
注册表文件:              .trae/agents/_AGENT_REGISTRY.json            (v4.0 科学智能调度版)
```

## 🧬 多维度联动矩阵 (v4.2 扩展)

### 记忆层亲和度

| Agent | 主读层 | 主写层 | 次读层 | 次写层 |
|-------|--------|--------|--------|--------|
| 天机 | L5 | L5 | L3,L4 | L3 |
| 铁卫 | L3,L4 | L3 | L5 | L5 |
| 忆库 | L0-L5 | L0-L5 | - | - |
| 洞察 | L0,L1 | L1 | L2,L3 | L0 |
| 律令 | L5 | L5 | L4 | L3 |
| 灵犀 | L1,L2 | L1 | L0 | L0 |
| 万象 | L0 | L0,L1 | L4 | L4 |
| 天枢 | L3,L4,L5 | L1,L3 | L0-L2 | L5 |
| 文宗 | L3,L4 | L3 | L5 | L5 |
| 经纬 | L4,L5 | L4,L5 | L3 | L3 |
| 妙笔 | L3,L4 | L3 | L1,L2 | L1 |
| 明镜 | L3,L4,L5 | L3 | L1 | L1 |
| 天算 | L4,L5 | L3,L4 | L3 | L1 |
| 矿师 | L0,L1 | L1,L4 | L4 | L3 |
| 连理 | L4 | L4 | L3 | L3 |
| 百巧 | L1 | L1 | L4 | - |
| 史官 | L3,L5 | L3,L5 | L4 | L4 |
| 锦书 | L1,L3 | L1 | L4 | - |
| 化生 | L5,L4 | L5,L3 | L3 | L4 |
| 千里 | L1,L5 | L1,L3 | L3 | L5 |
| 工造 | L5 | L5,L3 | L3 | L1 |
| 镇山 | L5 | L5,L3 | L3 | L1 |
| 追光 | L3,L5 | L3,L5 | L1 | L1 |

### 技能归属映射

| 技能 | 归属Agent |
|------|----------|
| tianji-orchestrate | 天机, 天枢 |
| system-diagnose | 天机, 千里 |
| agent-dispatch | 天枢 |
| skill-route | 百巧, 天枢 |
| context-extract | 洞察 |
| dialogue-quality | 洞察, 灵犀 |
| memory-remember/recall | 忆库 |
| auto-memory-capture | 忆库 |
| corpus-batch-import/extract | 矿师, 万象 |
| corpus-quality-score | 矿师, 天算 |
| data-analyze | 天算 |
| editor-review | 文宗, 明镜 |
| novel-* | 妙笔, 明镜, 锦书, 文宗, 史官 |
| ops-deploy | 工造 |
| perf-profile | 追光 |
| rule-check | 律令, 铁卫, 明镜, 简衡 |
| security-audit | 镇山 |
| test-gate | 铁卫 |

### CLEAR评估维度映射 (v4.2 新增)

| Agent | Cost(成本) | Latency(延迟) | Efficacy(效能) | Assurance(安全) | Reliability(可靠) |
|-------|-----------|---------------|----------------|-----------------|------------------|
| 天机 | 系统资源占用 | 全局调度延迟 | 决策正确率 | 系统安全状态 | 连续运行时间 |
| 铁卫 | 测试执行成本 | 门禁检查时间 | 门禁通过率 | 安全漏洞数 | 测试一致性 |
| 忆库 | 存储+检索成本 | 记忆读写延迟 | 检索命中率 | 数据加密状态 | 数据完整性 |
| 洞察 | 分析计算成本 | 意图识别时间 | 分类准确率 | 上下文隐私 | 识别稳定性 |
| 律令 | 规则匹配成本 | 合规检查时间 | 规则覆盖率 | 规则冲突率 | 检查一致性 |
| 灵犀 | 监控计算成本 | 异常检测时间 | 完整性评分 | 会话隐私 | 上下文恢复率 |
| 万象 | 多模态处理成本 | 解析处理时间 | 分类准确率 | 模态安全 | 解析成功率 |
| 天枢 | 调度计算成本 | 任务分派时间 | 调度准确率 | 调度安全 | SLA合规率 |
| 文宗 | 项目管理成本 | 审核反馈时间 | 项目准时率 | 内容合规 | 团队协调效率 |
| 经纬 | 架构设计成本 | 方案生成时间 | 设计通过率 | 架构安全 | 重构成功率 |
| 妙笔 | 创作计算成本 | 内容生成时间 | 创作质量分 | 内容安全 | 一致性评分 |
| 明镜 | 审校计算成本 | 审校反馈时间 | 质量评分 | 审校合规 | 审校一致性 |
| 天算 | 数据分析成本 | 查询响应时间 | 分析准确率 | 数据安全 | 结果一致性 |
| 矿师 | 语料处理成本 | 处理耗时 | 语料质量分 | 语料合规 | 处理成功率 |
| 连理 | 图谱构建成本 | 查询响应时间 | 关联准确率 | 知识安全 | 查询一致性 |
| 百巧 | 技能执行成本 | 工具调用时间 | 技能成功率 | 执行安全 | 结果可复现 |
| 史官 | 版本追踪成本 | 归档耗时 | 归档完整性 | 数据安全 | 版本一致性 |
| 锦书 | 导出处理成本 | 格式转换时间 | 格式合规率 | 导出安全 | 跨平台兼容 |
| 化生 | 进化计算成本 | 进化周期 | 进化成功率 | 进化风险 | 改进有效性 |
| 千里 | 监控计算成本 | 告警延迟 | 告警准确率 | 监控安全 | 监控覆盖率 |
| 工造 | 部署执行成本 | 部署耗时 | 部署成功率 | 部署安全 | 环境一致性 |
| 镇山 | 安全扫描成本 | 扫描耗时 | 漏洞检出率 | 合规覆盖率 | 误报率 |
| 追光 | 性能分析成本 | 剖析耗时 | 瓶颈定位率 | 性能安全 | 基准一致性 |
| UI设计师 | 设计计算成本 | 设计输出时间 | 设计质量分 | 设计合规 | 设计一致性 |
| 前端架构师 | 架构设计成本 | 方案生成时间 | 设计通过率 | 代码安全 | 架构稳定性 |
| 后端架构师 | 架构设计成本 | 方案生成时间 | 设计通过率 | API安全 | 架构稳定性 |
| API测试专家 | 测试执行成本 | 测试耗时 | 测试覆盖率 | 测试安全 | 结果可复现 |
| AI集成工程师 | 集成开发成本 | 集成耗时 | 集成成功率 | 集成安全 | 集成稳定性 |
| 性能优化专家 | 分析优化成本 | 分析耗时 | 优化效果 | 性能安全 | 基准一致性 |
| 合规检查专家 | 合规检查成本 | 检查耗时 | 合规通过率 | 安全合规 | 检查一致性 |

> **版本**: 4.2.0-科学智能调度扩展 | **生效**: 2026-07-02 | **方案**: A-中文主名 | **状态**: ✅ 已实施
