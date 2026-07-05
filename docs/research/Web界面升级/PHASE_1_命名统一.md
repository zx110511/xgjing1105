# 🌐 天机v9.1 Web界面史诗级升级指令集

**版本**: v1.0  
**创建时间**: 2026-05-25  
**目标**: 全覆盖实现 `d:\元初系统\天机v9.1` Web交互界面  
**依据**: [天机v9.1落地开发通用指令] + [专业化集成与托盘定制指令集]

---

## 📊 当前状态审计（基于截图分析）

### 已完成项

| 组件 | 状态 | 说明 |
|------|------|------|
| React + TypeScript 框架 | ✅ | Vite + Ant Design 5 |
| MainLayout 主布局 | ✅ | 左侧导航 + Header |
| Dashboard 仪表盘 | ⚠️ | UI完成，数据离线 |
| MemoryManagement 记忆管理 | ⚠️ | UI完成，需验证 |
| KnowledgeGraph 知识图谱 | ⚠️ | UI完成，需验证 |
| SystemConfig 系统配置 | ⚠️ | UI完成，需验证 |
| Monitoring 监控日志 | ⚠️ | UI完成，需验证 |
| API 服务层 | ✅ | axios 封装完成 |

### 核心问题：所有组件显示"离线"

```
┌─────────────────────────────────────────────────────────────┐
│  当前问题: 15个模块全部显示 "离线"                           │
│                                                               │
│  自动捕获        → 离线                                      │
│  备份管理器      → 离线                                      │
│  DeepSeek大脑    → 离线                                      │
│  Trae对话捕获    → 离线                                      │
│  强制记录钩子    → 离线                                      │
│  技能提取流水线   → 离线                                      │
│  智能调度器      → 离线                                      │
│  TVP协议桥接     → 离线                                      │
│  Agent调度器     → 离线                                      │
│  异步桥接层      → 离线                                      │
│  技能注册表      → 离线                                      │
│  学习引擎        → 离线                                      │
│  工作流引擎      → 离线                                      │
│  消息网关        → 离线                                      │
│  进化引擎        → 离线                                      │
│  进化循环        → 离线                                      │
└─────────────────────────────────────────────────────────────┘
```

### 根因分析

1. **前端 API 调用正常** - /api/health 返回 200
2. **后端服务运行中** - PID 186728, 端口 8770 Listen
3. **模块状态 API 缺失或返回格式不匹配**

---

## 🎯 史诗级升级规划（5大阶段）

### Phase 1: 命名统一 + 基础修复 (P0)

**目标**: 统一品牌标识，修复基础问题

| 任务 | 文件 | 状态 |
|------|------|------|
| 1.1 浏览器标题修复 | web/index.html | ✅ |
| 1.2 Dashboard 标题修复 | web/src/pages/Dashboard.tsx | ✅ |
| 1.3 server/main.py 服务名修复 | server/main.py | ✅ |
| 1.4 UserGuide.tsx 引导文案修复 | web/src/components/UserGuide.tsx | ✅ |
| 1.5 package.json 描述修复 | web/package.json | ✅ |
| 1.6 Dockerfile 标签修复 | Dockerfile | ✅ |
| 1.7 ws_routes.py 连接消息修复 | server/api/ws_routes.py | ✅ |
| 1.8 tests/sss_test_api.py 断言修复 | tests/sss_test_api.py | ✅ |

**验收标准**:
```powershell
# 浏览器访问 http://127.0.0.1:8770/dashboard
# 标签页应显示: "天机v9.1 元初系统 · 智能记忆平台"
# 页面标题: "天机 v9.1 元初系统 · 智能记忆平台"
```

---

### Phase 2: 模块状态在线化 (P0) 🔥核心

**目标**: 15个模块从"离线"→"在线"，显示真实数据

#### 2.1 后端 API 补齐

| API 端点 | 方法 | 用途 | 优先级 |
|---------|------|------|--------|
| `/api/status/full` | GET | 全量模块状态 | P0 |
| `/api/system/stats` | GET | 系统统计 | P0 |
| `/api/ops/report` | GET | 运维报告 | P0 |
| `/api/container/health` | GET | 容器健康 | P0 |
| `/api/memory/stats` | GET | 记忆统计 | P0 |

#### 2.2 前端数据适配

| 任务 | 文件 | 说明 |
|------|------|------|
| 2.2.1 | web/src/services/api.ts | 确保 baseURL = '/api' |
| 2.2.2 | web/src/config/api.config.ts | 验证端点配置 |
| 2.2.3 | web/src/pages/Dashboard.tsx | 适配真实 API 响应格式 |
| 2.2.4 | web/src/pages/Monitoring.tsx | 适配监控 API |

#### 2.3 模块状态映射表

```
前端 MODULE_CONFIG_3D          → 后端 TianjiContainer 模块
─────────────────────────────────────────────────────────
auto_capture                  → InterceptLayer (M14)
backup_manager                → BackupManager (TianjiDaemon)
deepseek_driver                → DeepSeekDriver (M15)
trae_conversation_capture     → MessageGateway (M11)
enforcement_hook               → EnforcementHook (M13)
skill_pipeline                → SkillRegistry (M4)
intelligent_scheduler         → IntelligentScheduler (M9)
tvp_bridge                    → TVPBridge (M16)
agent_scheduler               → AgentOrchestrator (M34)
async_bridge                  → AsyncBridge (M26)
skill_registry                → SkillRegistry (M4)
learning_engine               → LearningEngine (M8)
workflow_engine               → WorkflowEngine (M10)
message_gateway               → MessageGateway (M11)
evolution_engine              → EvolutionEngine (M7)
evolution_loop                → EvolutionLoop (M9)
```

**验收标准**:
```javascript
// Dashboard 应显示:
// 自动捕获: 在线 (captured: 7, stored: 5, errors: 0)
// DeepSeek大脑: 在线 (events: 120, decisions: 45, ready: true)
// 智能调度器: 在线 (tasks: 12, delegated: 8, success: 95%)
```

---

### Phase 3: 五大页面功能补齐 (P1)

#### 3.1 仪表盘 (/dashboard)

| 功能 | 状态 | 实现 |
|------|------|------|
| 实时状态 Tab | ⚠️ UI完成 | 需接入真实数据 |
| 累计数据 Tab | ⚠️ UI完成 | 需接入真实数据 |
| 历史趋势 Tab | ⚠️ UI完成 | 需接入真实数据 |
| 模块卡片点击详情 | ❌ 未实现 | 弹窗展示详细指标 |
| 刷新按钮 | ✅ 已有 | 手动刷新 |
| 自动刷新 | ✅ 已有 | 10s间隔 |

**新增功能**:
- [ ] 模块卡片点击 → Modal 展示详细指标
- [ ] 快捷操作栏 (重启模块/查看日志/进入配置)
- [ ] 告警阈值可视化 (红/黄/绿状态指示)

#### 3.2 记忆管理 (/memory)

| 功能 | 状态 | 实现 |
|------|------|------|
| 记忆列表 | ⚠️ UI完成 | 需接入 CRUD API |
| 新建记忆 | ⚠️ UI完成 | 需接入 POST /api/memories |
| 编辑记忆 | ⚠️ UI完成 | 需接入 PUT /api/memories/{id} |
| 删除记忆 | ⚠️ UI完成 | 需接入 DELETE /api/memories/{id} |
| 高级搜索 | ⚠️ UI完成 | 需接入 POST /api/search |
| 批量操作 | ⚠️ UI完成 | 需接入批量 API |
| 六层筛选 | ⚠️ UI完成 | L0-L5 层级筛选 |

**新增功能**:
- [ ] 记忆详情弹窗 (完整字段展示)
- [ ] 语义搜索结果高亮
- [ ] 记忆关联图谱 (related_ids 可视化)
- [ ] 记忆溯源链路 (explain_memory_lineage)

#### 3.3 知识图谱 (/knowledge-graph)

| 功能 | 状态 | 实现 |
|------|------|------|
| 力导向图 | ⚠️ UI完成 | 需接入知识图谱 API |
| 节点详情 | ⚠️ UI完成 | 需接入实体查询 |
| 关系类型筛选 | ⚠️ UI完成 | 需接入边类型过滤 |
| 搜索节点 | ⚠️ UI完成 | 需接入图谱搜索 |
| 图谱统计 | ⚠️ UI完成 | 节点数/边数/密度 |

**新增功能**:
- [ ] 知识三元组表格视图
- [ ] 实体关系时间线
- [ ] DeepSeek 知识抽取集成
- [ ] 图谱导出 (JSON/GraphML)

#### 3.4 系统配置 (/config)

| 功能 | 状态 | 实现 |
|------|------|------|
| ICME六层参数 | ⚠️ UI完成 | 需接入配置读写 API |
| MCP Server配置 | ⚠️ UI完成 | 需接入 mcp.json 管理 |
| Agent配置 | ⚠️ UI完成 | 需接入 Agent 注册表 |
| Skills配置 | ⚠️ UI完成 | 需接入技能注册表 |
| 系统信息 | ⚠️ UI完成 | 版本/运行时间/端口 |

**新增功能**:
- [ ] 配置热重载 (修改后立即生效)
- [ ] 配置导入/导出
- [ ] 配置变更历史 (版本对比)
- [ ] 配置验证提示 (实时校验)

#### 3.5 监控日志 (/monitoring)

| 功能 | 状态 | 实现 |
|------|------|------|
| 系统健康 | ⚠️ UI完成 | /api/health 数据 |
| 运行时间 | ⚠️ UI完成 | uptime_seconds |
| 记忆总量 | ⚠️ UI完成 | memory stats |
| 模块在线率 | ⚠️ UI完成 | container health |
| 各层分布 | ⚠️ UI完成 | layer stats |
| 日志列表 | ❌ 未实现 | tray.log 流式读取 |
| 异常检测 | ❌ 未实现 | ops anomalies |

**新增功能**:
- [ ] 实时日志流 (WebSocket 推送)
- [ ] 日志级别筛选 (DEBUG/INFO/WARN/ERROR)
- [ ] 日志关键词搜索
- [ ] 异常告警面板 (自动刷新)
- [ ] 自愈历史记录

---

### Phase 4: 架构补齐 (P1)

#### 4.1 WebSocket 实时推送

```
当前: HTTP 轮询 (10s间隔)
目标: WebSocket 双向通信

实现:
  ws://127.0.0.1:8770/ws/connect
    ↓
  实时事件流:
    - module_status_change (模块状态变更)
    - new_memory (新记忆创建)
    - alert_threshold (告警触发)
    - log_entry (日志条目)
```

#### 4.2 API 层完整性检查

| 缺失API | 优先级 | 说明 |
|---------|--------|------|
| GET /api/modules | P0 | 模块列表+状态 |
| GET /api/modules/{id}/detail | P1 | 单模块详细信息 |
| POST /api/modules/{id}/restart | P1 | 重启模块 |
| GET /api/logs/stream | P1 | 日志流式读取 |
| GET /api/alerts | P1 | 告警列表 |
| PUT /api/config/{section} | P2 | 配置更新 |

#### 4.3 前端状态管理优化

```
当前: 组件内 useState
目标: Zustand/Pinia 全局状态 store

stores/
  ├── useDashboardStore.ts    # 仪表盘状态
  ├── useMemoryStore.ts       # 记忆管理状态
  ├── useConfigStore.ts       # 配置状态
  └── useMonitoringStore.ts   # 监控状态
```

---

### Phase 5: 体验优化 (P2)

#### 5.1 视觉升级

- [ ] 深色模式支持 (Ant Design ConfigProvider)
- [ ] 自定义主题色 (天机紫 #722ed1 渐变)
- [ ] 动画过渡 (页面切换/数据加载)
- [ ] 响应式布局 (移动端适配)

#### 5.2 性能优化

- [ ] 虚拟滚动 (大量记忆列表)
- [ ] API 请求缓存 (SWR/stale-while-revalidate)
- [ ] 图片懒加载 (知识图谱节点图标)
- [ ] 代码分割 (React.lazy 路由级)

#### 5.3 可访问性

- [ ] 键盘快捷键 (Ctrl+K 搜索, Ctrl+N 新建)
- [ ] ARIA 标签完善
- [ ] 高对比度模式支持

---

## 📁 文件存储位置规划

```
d:\元初系统\天机v9.1\
├── 天机v9.1科研区\
│   └── Web界面升级\
│       ├── PHASE_1_命名统一.md          # 本文件
│       ├── PHASE_2_模块在线化.md        # 待生成
│       ├── PHASE_3_五页面补齐.md        # 待生成
│       ├── PHASE_4_架构补齐.md         # 待生成
│       └── PHASE_5_体验优化.md          # 待生成
│
├── web\src\
│   ├── pages\
│   │   ├── Dashboard.tsx             # 仪表盘 (重点改造)
│   │   ├── MemoryManagement.tsx       # 记忆管理
│   │   ├── KnowledgeGraph.tsx        # 知识图谱
│   │   ├── SystemConfig.tsx           # 系统配置
│   │   └── Monitoring.tsx             # 监控日志
│   ├── services\
│   │   ├── api.ts                    # API 客户端 (需扩展)
│   │   ├── memory-service.ts          # 记忆服务
│   │   └── search-service.ts          # 搜索服务
│   ├── stores\                        # 新增: 全局状态管理
│   ├── components\
│   │   ├── ModuleCard.tsx            # 新增: 模块卡片组件
│   │   ├── StatusIndicator.tsx        # 新增: 状态指示器
│   │   └── RealtimeChart.tsx          # 新增: 实时图表
│   └── layouts\
│       └── MainLayout.tsx            # 主布局 (已完善)
│
└── server\
    ├── api\
    │   ├── status_routes.py           # 新增: 模块状态 API
    │   └── websocket_routes.py        # 新增: WS 推送
    └── main.py                       # FastAPI 入口 (已修复)
```

---

## 🚀 执行顺序建议

```
Phase 1 (命名统一)     → 30分钟 → 立即可执行
    ↓
Phase 2 (模块在线化)   → 2小时 → 核心优先
    ↓
Phase 3 (五页面补齐)   → 4小时 → 分页面迭代
    ↓
Phase 4 (架构补齐)     → 3小时 → 基础设施
    ↓
Phase 5 (体验优化)     → 2小时 → 锦上添花
```

---

## ✅ Phase 1 完成清单

- [x] 1.1 浏览器标题修复 (web/index.html)
- [x] 1.2 Dashboard 标题修复 (web/src/pages/Dashboard.tsx)
- [x] 1.3 server/main.py 服务名修复
- [x] 1.4 UserGuide.tsx 引导文案修复
- [x] 1.5 package.json 描述修复
- [x] 1.6 Dockerfile 标签修复
- [x] 1.7 ws_routes.py 连接消息修复
- [x] 1.8 tests/sss_test_api.py 断言修复

---

**下一步**: 执行 Phase 2 (模块状态在线化)，修复 15 个模块的"离线"状态
