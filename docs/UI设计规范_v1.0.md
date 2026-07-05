# AI记忆系统 - UI/UX设计规范 v1.0

> **版本**: v1.0.0 | **制定日期**: 2026-05-03 | **制定者**: @planner  
> **项目**: AI记忆系统 Web界面 | **技术栈**: React 18 + TypeScript 5 + Ant Design 5

---

## 📋 设计原则

### 核心设计理念

1. **简洁至上**: 减少视觉噪音，突出核心功能
2. **一致性**: 统一的设计语言和交互模式
3. **可访问性**: 符合WCAG 2.1 AA标准
4. **响应式**: 适配桌面、平板、移动设备
5. **性能优先**: 快速加载，流畅交互

### 设计价值观

- **用户中心**: 以用户需求为导向
- **数据驱动**: 基于数据优化设计
- **渐进增强**: 核心功能优先，高级特性渐进
- **容错设计**: 友好的错误提示和恢复机制

---

## 🎨 视觉设计系统

### 色彩系统

#### 主色调

```css
/* 主色 - 科技蓝 */
--primary-color: #1890ff;
--primary-hover: #40a9ff;
--primary-active: #096dd9;
--primary-bg: #e6f7ff;

/* 辅助色 */
--success-color: #52c41a;
--warning-color: #faad14;
--error-color: #ff4d4f;
--info-color: #1890ff;

/* 中性色 */
--text-primary: rgba(0, 0, 0, 0.85);
--text-secondary: rgba(0, 0, 0, 0.65);
--text-disabled: rgba(0, 0, 0, 0.25);
--border-color: #d9d9d9;
--background-color: #f0f2f5;
```

#### 语义化色彩

| 颜色类型 | 色值 | 使用场景 |
|---------|------|---------|
| **记忆层级色彩** | | |
| Sensory (感知) | `#722ed1` | 即时输入捕获 |
| Working (工作) | `#1890ff` | 会话上下文 |
| Short-term (短期) | `#13c2c2` | 关键信息保持 |
| Episodic (情景) | `#52c41a` | 决策记录/AI经验 |
| Semantic (语义) | `#fa8c16` | 知识图谱/概念 |
| Meta (元记忆) | `#eb2f96` | 策略自优化 |

### 字体系统

```css
/* 字体家族 */
--font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 
               'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', 
               Helvetica, Arial, sans-serif;

/* 字体大小 */
--font-size-xs: 12px;
--font-size-sm: 14px;
--font-size-base: 16px;
--font-size-lg: 18px;
--font-size-xl: 20px;
--font-size-xxl: 24px;

/* 行高 */
--line-height-base: 1.5;
--line-height-lg: 1.75;

/* 字重 */
--font-weight-normal: 400;
--font-weight-medium: 500;
--font-weight-semibold: 600;
--font-weight-bold: 700;
```

### 间距系统

```css
/* 基础间距单位: 4px */
--spacing-xs: 4px;
--spacing-sm: 8px;
--spacing-md: 12px;
--spacing-base: 16px;
--spacing-lg: 24px;
--spacing-xl: 32px;
--spacing-xxl: 48px;
```

### 圆角系统

```css
--border-radius-sm: 2px;
--border-radius-base: 4px;
--border-radius-lg: 8px;
--border-radius-xl: 12px;
--border-radius-round: 50%;
```

### 阴影系统

```css
/* 卡片阴影 */
--shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.03), 
             0 1px 6px -1px rgba(0, 0, 0, 0.02), 
             0 2px 4px 0 rgba(0, 0, 0, 0.02);

--shadow-base: 0 6px 16px 0 rgba(0, 0, 0, 0.08),
               0 3px 6px -4px rgba(0, 0, 0, 0.12),
               0 9px 28px 8px rgba(0, 0, 0, 0.05);

--shadow-lg: 0 6px 16px 8px rgba(0, 0, 0, 0.08),
             0 3px 6px 4px rgba(0, 0, 0, 0.12),
             0 9px 28px 16px rgba(0, 0, 0, 0.05);
```

---

## 📐 布局系统

### 栅格系统

```css
/* 24栅格系统 */
.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 16px;
}

/* 响应式断点 */
--breakpoint-xs: 480px;
--breakpoint-sm: 576px;
--breakpoint-md: 768px;
--breakpoint-lg: 992px;
--breakpoint-xl: 1200px;
--breakpoint-xxl: 1600px;
```

### 页面布局

```
┌─────────────────────────────────────────────────────┐
│ Header (64px)                                        │
│ - Logo + 导航 + 用户信息                              │
├──────────┬──────────────────────────────────────────┤
│ Sidebar  │ Main Content                             │
│ (200px)  │                                          │
│          │ ┌──────────────────────────────────────┐ │
│ - 仪表盘  │ │ Breadcrumb + Page Title              │ │
│ - 记忆管理│ └──────────────────────────────────────┘ │
│ - 知识图谱│                                          │
│ - 系统配置│ ┌──────────────────────────────────────┐ │
│ - 监控    │ │ Content Area                         │ │
│          │ │                                      │ │
│          │ │                                      │ │
│          │ └──────────────────────────────────────┘ │
└──────────┴──────────────────────────────────────────┘
```

---

## 🧩 组件设计规范

### 基础组件

#### Button 按钮

```tsx
// 按钮类型
type ButtonType = 'primary' | 'default' | 'dashed' | 'text' | 'link';

// 按钮尺寸
type ButtonSize = 'large' | 'middle' | 'small';

// 使用规范
- Primary: 主要操作（提交、确认）
- Default: 次要操作（取消、返回）
- Dashed: 添加操作
- Text: 文本按钮
- Link: 链接按钮

// 尺寸规范
- Large: 高度 40px, padding 12px 24px
- Middle: 高度 32px, padding 8px 16px
- Small: 高度 24px, padding 4px 8px
```

#### Input 输入框

```tsx
// 输入框尺寸
type InputSize = 'large' | 'middle' | 'small';

// 使用规范
- 搜索框: 带搜索图标，支持清除
- 文本框: 带字数统计
- 密码框: 带显示/隐藏切换

// 尺寸规范
- Large: 高度 40px
- Middle: 高度 32px
- Small: 高度 24px
```

#### Card 卡片

```tsx
// 卡片结构
<Card>
  <CardHeader title="标题" extra={<Button>操作</Button>} />
  <CardDivider />
  <CardBody>
    {/* 内容 */}
  </CardBody>
  <CardFooter>
    {/* 底部操作 */}
  </CardFooter>
</Card>

// 样式规范
- 背景: #ffffff
- 圆角: 8px
- 阴影: shadow-base
- 内边距: 24px
```

### 业务组件

#### MemoryCard 记忆卡片

```tsx
interface MemoryCardProps {
  id: string;
  content: string;
  layer: 'sensory' | 'working' | 'short_term' | 'episodic' | 'semantic' | 'meta';
  tags: string[];
  priority: 'low' | 'medium' | 'high' | 'critical';
  createdAt: Date;
  onEdit: (id: string) => void;
  onDelete: (id: string) => void;
}

// 设计规范
- 卡片高度: 最小 120px, 最大 300px
- 内容截断: 超过3行显示"展开"
- 层级标识: 左侧色条 (4px宽)
- 标签显示: 最多显示3个，超过显示"+N"
```

#### KnowledgeGraph 知识图谱

```tsx
interface KnowledgeGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeClick: (node: GraphNode) => void;
  onEdgeClick: (edge: GraphEdge) => void;
}

// 设计规范
- 节点类型: 实体(圆形)、概念(方形)、事件(菱形)
- 节点大小: 根据重要度动态调整
- 连线样式: 实线(强关联)、虚线(弱关联)
- 交互: 拖拽、缩放、点击高亮
```

---

## 🎭 交互设计规范

### 反馈机制

#### Toast 通知

```tsx
// 成功通知
message.success('操作成功');

// 错误通知
message.error('操作失败，请重试');

// 警告通知
message.warning('请注意数据安全');

// 信息通知
message.info('系统将在5分钟后维护');

// 规范
- 显示位置: 顶部居中
- 自动关闭: 3秒
- 最大显示: 3条
- 支持手动关闭
```

#### Modal 对话框

```tsx
// 确认对话框
Modal.confirm({
  title: '确认删除',
  content: '删除后数据无法恢复，确定要删除吗？',
  okText: '确认',
  cancelText: '取消',
  onOk: () => {},
});

// 规范
- 宽度: 520px
- 遮罩: 黑色半透明 (rgba(0,0,0,0.45))
- 动画: 淡入淡出 (300ms)
- 支持ESC关闭
```

#### Loading 加载

```tsx
// 页面加载
<Spin size="large" tip="加载中..." />

// 按钮加载
<Button type="primary" loading>
  提交中
</Button>

// 规范
- 页面加载: 居中显示
- 按钮加载: 替换按钮文字
- 列表加载: 骨架屏
```

### 动画规范

```css
/* 过渡动画 */
transition: all 0.3s cubic-bezier(0.645, 0.045, 0.355, 1);

/* 淡入淡出 */
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* 滑动 */
@keyframes slideIn {
  from { transform: translateY(-10px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

/* 缩放 */
@keyframes zoomIn {
  from { transform: scale(0.8); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}
```

---

## 📱 响应式设计

### 断点设计

| 设备类型 | 断点 | 布局调整 |
|---------|------|---------|
| **手机** | < 576px | 单列布局，隐藏侧边栏 |
| **平板** | 576px - 768px | 两列布局，可折叠侧边栏 |
| **桌面** | 768px - 992px | 三列布局，固定侧边栏 |
| **大屏** | > 992px | 四列布局，固定侧边栏 |

### 移动端适配

```tsx
// 移动端导航
<Drawer
  placement="left"
  visible={drawerVisible}
  onClose={() => setDrawerVisible(false)}
>
  <Menu mode="inline" />
</Drawer>

// 移动端卡片
<List
  grid={{ gutter: 16, xs: 1, sm: 2, md: 3, lg: 4 }}
  dataSource={memories}
  renderItem={memory => (
    <List.Item>
      <MemoryCard {...memory} />
    </List.Item>
  )}
/>
```

---

## ♿ 可访问性设计

### ARIA 标签

```tsx
// 按钮标签
<Button aria-label="创建新记忆">
  <PlusOutlined />
</Button>

// 导航标签
<nav aria-label="主导航">
  <Menu />
</nav>

// 表单标签
<Form.Item label="记忆内容" name="content">
  <Input.TextArea aria-describedby="content-hint" />
  <span id="content-hint">请输入要存储的记忆内容</span>
</Form.Item>
```

### 键盘导航

```tsx
// 快捷键支持
- Tab: 焦点切换
- Enter: 确认操作
- Esc: 关闭对话框
- Arrow Keys: 列表导航
- Ctrl/Cmd + S: 保存
- Ctrl/Cmd + F: 搜索
```

### 颜色对比度

```css
/* 文本对比度 >= 4.5:1 */
--text-primary: rgba(0, 0, 0, 0.85); /* 对比度: 14.63:1 */
--text-secondary: rgba(0, 0, 0, 0.65); /* 对比度: 9.25:1 */

/* 大文本对比度 >= 3:1 */
--text-large: rgba(0, 0, 0, 0.85); /* 对比度: 14.63:1 */
```

---

## 📊 数据可视化规范

### 图表设计

#### 记忆统计图表

```tsx
// 柱状图 - 记忆数量分布
<BarChart
  data={memoryStats}
  xField="layer"
  yField="count"
  colorField="layer"
  color={layerColors}
/>

// 折线图 - 记忆增长趋势
<LineChart
  data={memoryTrend}
  xField="date"
  yField="count"
  smooth={true}
/>

// 饼图 - 记忆类型占比
<PieChart
  data={memoryTypes}
  angleField="count"
  colorField="type"
  radius={0.8}
/>
```

### 知识图谱可视化

```tsx
// D3.js 图谱
<ForceGraph
  nodes={graphNodes}
  edges={graphEdges}
  nodeColor={nodeColorByType}
  nodeSize={nodeSizeByImportance}
  linkWidth={linkWidthByStrength}
/>

// Cytoscape.js 图谱
<CytoscapeComponent
  elements={graphElements}
  layout={{ name: 'cose' }}
  style={graphStyles}
/>
```

---

## 🎯 页面设计规范

### 仪表盘 (Dashboard)

```
┌─────────────────────────────────────────────────────┐
│ 系统状态概览                                          │
├─────────────┬─────────────┬─────────────┬───────────┤
│ 总记忆数     │ 今日新增     │ 知识节点     │ 系统健康   │
│ 1,234       │ 56          │ 892         │ 98%       │
├─────────────┴─────────────┴─────────────┴───────────┤
│ 记忆增长趋势图                                        │
│ [折线图]                                              │
├───────────────────────────────┬─────────────────────┤
│ 记忆层级分布                   │ 快速操作             │
│ [饼图]                         │ - 创建记忆           │
│                                │ - 搜索记忆           │
│                                │ - 导入数据           │
│                                │ - 查看图谱           │
└───────────────────────────────┴─────────────────────┘
```

### 记忆管理页面

```
┌─────────────────────────────────────────────────────┐
│ 记忆管理                                    [+创建]  │
├─────────────────────────────────────────────────────┤
│ [搜索框] [层级筛选▼] [标签筛选▼] [时间筛选▼]        │
├─────────────────────────────────────────────────────┤
│ ┌───────────────────────────────────────────────┐   │
│ │ [Sensory] 这是一个重要的项目决策...            │   │
│ │ 标签: 项目, 决策 | 优先级: 高 | 2026-05-03    │   │
│ │                              [编辑] [删除]    │   │
│ └───────────────────────────────────────────────┘   │
│ ┌───────────────────────────────────────────────┐   │
│ │ [Episodic] 用户偏好使用Python进行数据分析...   │   │
│ │ 标签: 用户偏好, Python | 优先级: 中 | 2026-05-02│   │
│ │                              [编辑] [删除]    │   │
│ └───────────────────────────────────────────────┘   │
│                                                      │
│ [上一页] 1 2 3 ... 10 [下一页]                      │
└─────────────────────────────────────────────────────┘
```

---

## 📝 文案规范

### 文案风格

- **简洁明了**: 避免冗长，直击要点
- **用户视角**: 使用"您"而非"用户"
- **积极正面**: 强调成功而非失败
- **一致性**: 统一术语和表达方式

### 常用文案

```yaml
# 按钮文案
create: 创建
edit: 编辑
delete: 删除
save: 保存
cancel: 取消
confirm: 确认
search: 搜索
reset: 重置

# 提示文案
loading: 加载中...
success: 操作成功
error: 操作失败
confirm_delete: 确定要删除吗？删除后无法恢复。

# 空状态文案
no_data: 暂无数据
no_search_result: 未找到相关记忆
create_first: 创建第一条记忆
```

---

## 🛠️ 设计工具与资源

### 设计工具

- **Figma**: UI设计与原型
- **Sketch**: UI设计（备选）
- **Adobe XD**: UI设计（备选）

### 图标资源

- **Ant Design Icons**: 主要图标库
- **Font Awesome**: 补充图标
- **自定义图标**: 特殊业务图标

### 设计资源

- **Ant Design**: 组件库
- **Ant Design Pro**: 页面模板
- **Ant Design Charts**: 图表库

---

## 📐 设计交付物

### 设计文件

1. **UI设计规范文档** (本文档)
2. **Figma设计源文件**
3. **设计资源包** (图标、字体、色彩)
4. **交互原型** (可点击原型)

### 开发交付物

1. **组件库文档** (Storybook)
2. **设计Token** (CSS变量)
3. **图标库** (SVG Sprite)
4. **样式指南** (CSS/SCSS)

---

## 🎯 验收标准

### 设计验收

- ✅ 符合设计规范
- ✅ 响应式适配
- ✅ 可访问性达标
- ✅ 浏览器兼容

### 开发验收

- ✅ 像素级还原
- ✅ 交互流畅
- ✅ 性能优化
- ✅ 代码规范

---

## 📚 参考资料

- [Ant Design 设计语言](https://ant.design/docs/spec/introduce-cn)
- [Material Design](https://material.io/design)
- [Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/)
- [WCAG 2.1](https://www.w3.org/TR/WCAG21/)

---

**设计规范制定完成时间**: 2026-05-03  
**版本**: v1.0.0  
**状态**: ✅ 已完成  
**下一步**: 创建界面原型设计
