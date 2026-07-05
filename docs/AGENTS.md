# 天机-灵境 Agent 体系规范

> 本文件为 Qoder / Trae IDE 的 Agent 注册总览。
> 元初系统 v9.1 | 20 Agent | 4 层级 | AMIM M37 对齐

---

## 体系架构

```
L0 基础设施层 ── 铁卫(tiewei)     🛡️ 质量守护/门禁
L1 数据上下文层 ─┬─ 忆库(yiku)     💾 记忆架构师
                ├─ 洞察(dongcha)  🔎 上下文分析
                ├─ 律令(luling)   ⚖️ 规则守护
                ├─ 灵犀(lingxi)   🦋 会话监控
                └─ 万象(wanxiang) 👁️ 多模态感知
L2 决策创作层 ──┬─ 天枢(tianshu)   🎯 总指挥
                ├─ 文宗(wenzong)  📝 主编
                ├─ 妙笔(miaobi)   ✍️ 创作者
                ├─ 明镜(mingjing) 🔍 审校者
                ├─ 天算(tiansuan) 📊 数据分析师
                ├─ 经纬(jingwei)  📐 架构师
                ├─ 矿师(kuangshi) ⛏️ 语料处理
                └─ 连理(lianli)   🕸️ 知识图谱
L3 执行工具层 ──┬─ 百巧(baiqiao)   ⚡ 技能代理
                ├─ 史官(shiguan)  📜 版本追踪
                └─ 锦书(jinshu)   📖 成品导出
                └─ 化生(huasheng) 🧬 进化工程师
L4 运维观测层 ──┬─ 千里(qianli)   👁 系统监控
                ├─ 工造(gongzao)  🚀 DevOps
                ├─ 镇山(zhenshan) 🔒 安全审计
                └─ 追光(zhuiguang) ⚡ 性能优化
```

---

## Agent 速查表

| Agent | 代号 | 层级 | 角色 | 核心能力 | 主要工具 |
|-------|------|------|------|----------|----------|
| 铁卫 | tiewei | L0 | 质量守护 | SG门禁、功能验证、安全测试 | memory_recall, security-scanner, performance-profiler |
| 忆库 | yiku | L1 | 记忆架构师 | ICME六层管理、语义检索、巩固晋升 | memory_remember, memory_recall, search_memories, run_reflective_cycle |
| 洞察 | dongcha | L1 | 上下文分析师 | 意图识别、实体抽取、情感分析 | context_extract, tianji_classify, tianji_summarize_conversation |
| 律令 | luling | L1 | 规则守护者 | 规则匹配、合规检查、冲突检测 | rule_evaluate, security-scanner |
| 灵犀 | lingxi | L1 | 会话监控 | 对话完整性、意图连续性、异常检测 | context_extract, memory_recall, tianji_intercept |
| 万象 | wanxiang | L1 | 多模态感知师 | 图像理解、表格解析、模态分类 | memory_capture_multimodal, tianji_classify, tianji_extract_knowledge |
| 天枢 | tianshu | L2 | 总指挥 | 编排、决策、调度、分发 | agent_dispatch, system_status, memory_remember, execute_command |
| 文宗 | wenzong | L2 | 主编 | 项目管理、内容审核、进度追踪 | agent_dispatch, system_status, memory_recall |
| 妙笔 | miaobi | L2 | 创作者 | 创作、写作、创意生成、角色塑造 | memory_recall, memory_remember, tianji_semantic_search |
| 明镜 | mingjing | L2 | 审校者 | 审校、质量评估、一致性检查 | memory_recall, rule_evaluate, security-scanner |
| 天算 | tiansuan | L2 | 数据分析师 | 统计分析、可视化、模式识别 | memory_recall, memory_stats, tianji_summarize |
| 经纬 | jingwei | L2 | 架构师 | 架构设计、技术选型、路径规划 | agent_dispatch, rule_evaluate, memory_recall |
| 矿师 | kuangshi | L2 | 语料处理 | 语料导入、数据清洗、分类标注 | memory_remember, execute_command, tianji_auto_tag |
| 连理 | lianli | L2 | 知识图谱构建师 | 实体抽取、关系识别、图谱构建 | tianji_extract_knowledge, memory_build_graph, memory_query_graph |
| 百巧 | baiqiao | L3 | 技能代理 | 技能调用、工作流编排、参数验证 | execute_command, agent_dispatch |
| 史官 | shiguan | L3 | 版本追踪 | 版本管理、历史归档、变更分析 | memory_recall, memory_remember, tianji_export |
| 锦书 | jinshu | L3 | 成品导出 | 格式导出、成品美化、模板应用 | execute_command, memory_recall, tianji_export |
| 化生 | huasheng | L3 | 进化工程师 | 自我检查、自我更新、递归改进 | memory_evolve_self, memory_remember, execute_command |
| 千里 | qianli | L4 | 系统监控 | 实时监控、性能采集、智能告警 | system_status, performance-profiler, tianji_health |
| 工造 | gongzao | L4 | DevOps | CI/CD、环境管理、服务部署 | execute_command, ops-engine, agent_dispatch |
| 镇山 | zhenshan | L4 | 安全审计 | 漏洞扫描、合规检查、密钥管理 | security-scanner, execute_command |
| 追光 | zhuiguang | L4 | 性能优化 | 性能剖析、瓶颈分析、基准测试 | performance-profiler, execute_command |

---

## TVP 透明调度协议

每次 Agent 切换必须输出标准化声明：

```
[TVP] {emoji}@{name}({id}) → {tool_name} | stage={stage} | task={task_id}
```

示例：
```
[TVP] 🎯@天枢(tianshu) → agent_dispatch | stage=plan | task=proj-001
[TVP] ✍️@妙笔(miaobi) → memory_remember | stage=execute | task=proj-001
```

---

## 权限矩阵

| 调用者 | 可调用目标 | 限制说明 |
|--------|-----------|----------|
| @tianshu | 除自身外全部 | 总指挥，无限制 |
| @wenzong | @miaobi, @mingjing, @jinshu | 主编权限 |
| @miaobi | @yiku, @mingjing | 创作链路 |
| @mingjing | @yiku, @miaobi | 审校反馈 |
| @tiewei | @miaobi, @mingjing, @qianli | 测试门禁 |
| @jingwei | 全部Agent (只读咨询) | 规划咨询 |
| @lingxi | @yiku, @dongcha, @tianshu | 对话监控 |

> 未在矩阵中的调用组合 = **禁止**

---

## 协作模式

- **模式A 串行**: `A→B→C→D` — 严格顺序依赖
- **模式B 并行**: `→[A,B,C]→聚合` — 多维度独立分析
- **模式C 层级**: `主控→[子协调→工作者]` — 大型分治
- **模式D 工业化**: `S0→S1→...→S6` — 生产级交付

---

## 文件映射

| Agent | 运行时模块 | Trae配置 | Skill目录 |
|-------|-----------|----------|-----------|
| tianshu | [agents/tianshu.py](agents/tianshu.py) | [.trae/agents/trae-official-tianshu.json](.trae/agents/trae-official-tianshu.json) | agent-dispatch, agent-transparent-dispatch |
| yiku | [agents/yiku.py](agents/yiku.py) | [.trae/agents/trae-official-yiku.json](.trae/agents/trae-official-yiku.json) | memory-remember, memory-recall, auto-memory-capture |
| dongcha | [agents/dongcha.py](agents/dongcha.py) | [.trae/agents/trae-official-dongcha.json](.trae/agents/trae-official-dongcha.json) | context-extract, corpus-extract |
| qianli | [agents/qianli.py](agents/qianli.py) | [.trae/agents/trae-official-qianli.json](.trae/agents/trae-official-qianli.json) | system-diagnose |
| ... | ... | ... | ... |

完整注册表: [.trae/agents/_AGENT_REGISTRY.json](.trae/agents/_AGENT_REGISTRY.json)
技能清单: [.agents/skills/_manifest.json](.agents/skills/_manifest.json)

---

**版本**: v9.1.0 | **维护**: @tianshu + @yiku
