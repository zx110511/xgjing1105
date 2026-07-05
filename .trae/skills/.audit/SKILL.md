# 天机审计技能 (Tianji Audit Skill)

## 触发条件

- 用户请求审计、检查、诊断天机系统状态
- 系统发生异常需要追溯
- 定期健康检查

## 执行流程

1. 扫描天机 v8.1 核心模块完整性
2. 校验 ICME 六层记忆层数据一致性
3. 检查 MCP 服务器连接状态
4. 输出审计报告

## 审计范围

- `core/` — 核心引擎模块 (86 files)
- `agents/` — 28 Agent 代码
- `mcp/` — 6 MCP 服务器
- `server/` — API 服务 (port 8771)
- `.trae/agents/` — 23 Agent 配置
- `.trae/rules/` — 8 规则
- `.trae/skills/` — 18 技能
- `data/.memory/` — ICME 持久化数据

## 输出格式

```json
{
  "audit_time": "ISO8601",
  "modules": {
    "core": {"count": N, "status": "..."},
    "agents_code": {"count": N, "status": "..."},
    "agents_config": {"count": N, "status": "..."},
    "mcp": {"count": N, "status": "..."},
    "skills": {"count": N, "status": "..."}
  },
  "memory_health": {
    "L0_Sensory": "...",
    "L1_Working": "...",
    "L2_ShortTerm": "...",
    "L3_Episodic": "...",
    "L4_Semantic": "...",
    "L5_Meta": "..."
  },
  "issues": [],
  "score": "0-10"
}
```
