﻿﻿﻿import { useState, useEffect } from 'react'
import {
    Row,
    Col,
    Card,
    Tag,
    Spin,
    Alert,
    Tabs,
    Form,
    Input,
    InputNumber,
    Switch,
    Button,
    Space,
    Typography,
    Descriptions,
    message,
    Badge,
    Table,
    Empty,
    Slider,
    Segmented,
    Modal,
    Tooltip,
} from 'antd'
import type { SegmentedValue } from 'antd/es/segmented'
import {
    SaveOutlined,
    ReloadOutlined,
    SettingOutlined,
    ApiOutlined,
    RobotOutlined,
    ThunderboltOutlined,
    DatabaseOutlined,
    CheckCircleOutlined,
    CloseCircleOutlined,
    FileTextOutlined,
    BulbOutlined,
    EditOutlined,
    EyeOutlined,
    KeyOutlined,
    SafetyOutlined,
} from '@ant-design/icons'
import { api } from '../services/api'

const { Text } = Typography

interface McpServerItem {
    key: string
    name: string
    role: string
    exe: string
    enabled: boolean
    env: Record<string, string>
}

interface AgentItem {
    name: string
    role: string
    description: string
    enabled?: boolean
    priority?: number
}

interface SkillItem {
    name: string
    description: string
    layer: string
}

const LAYER_NAMES: Record<string, string> = {
    sensory: 'S 感知层',
    working: 'W 工作层',
    short_term: 'S-T 短期层',
    episodic: 'E 情景层',
    semantic: 'S 语义层',
    meta: 'M 元层',
}

interface LlmConfig {
    api_key?: string
    base_url?: string
    // [FIX-TS-021] 修复: temperature/max_tokens/top_p 改为可选 (允许部分配置)
    temperature?: number
    max_tokens?: number
    top_p?: number
    features?: {
        classify: boolean
        auto_tag: boolean
        summarize: boolean
        extract_knowledge: boolean
    }
}

interface ConfigData {
    memory?: {
        auto_capture_enabled: boolean
        layers: Record<string, { max_size: number; retention_hours: number }>
        backup_interval_minutes: number
        max_backup_count: number
    }
    api?: {
        base_url: string
        timeout_ms: number
        max_retries: number
    }
    mcp?: Record<string, { enabled: boolean }>
    monitoring?: {
        stats_interval_seconds: number
        health_check_interval_seconds: number
        history_retention_hours: number
    }
    agents?: Record<string, { enabled: boolean; priority: number }>
    llm?: LlmConfig
}

// ✅ DeepSeek V4-Pro/V4-Flash 配置
type DeepSeekModelMode = 'v4-flash' | 'v4-pro'
type DeepSeekReasoningEffort = 'low' | 'medium' | 'high'

interface DeepSeekConfig {
    apiKey: string
    apiKeyMasked: string
    defaultMode: DeepSeekModelMode
    thinkingEnabled: boolean
    reasoningEffort: DeepSeekReasoningEffort
    useLawPrompt: boolean
    systemPrompt: string
    lawRules: Array<{ id: string; name: string; description: string }>
}

const DEFAULT_DEEPSEEK_CONFIG: DeepSeekConfig = {
    apiKey: '',
    apiKeyMasked: '',
    defaultMode: 'v4-flash',
    thinkingEnabled: false,
    reasoningEffort: 'medium',
    useLawPrompt: true,
    systemPrompt: '',
    lawRules: [],
}

const DEEPSEEK_CONFIG_STORAGE_KEY = 'tianji_deepseek_config'

function maskApiKey(key: string): string {
    if (!key || key.length < 8) return key ? '****' : ''
    return `sk-****${key.slice(-4)}`
}

function loadDeepSeekConfigFromStorage(): Partial<DeepSeekConfig> {
    try {
        const stored = localStorage.getItem(DEEPSEEK_CONFIG_STORAGE_KEY)
        if (stored) {
            return JSON.parse(stored) as Partial<DeepSeekConfig>
        }
    } catch {
        // ignore parse errors
    }
    return {}
}

function saveDeepSeekConfigToStorage(config: Partial<DeepSeekConfig>): void {
    try {
        localStorage.setItem(DEEPSEEK_CONFIG_STORAGE_KEY, JSON.stringify(config))
    } catch {
        // ignore quota errors
    }
}

export default function SystemConfig() {
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [config, setConfig] = useState<ConfigData | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [form] = Form.useForm()
    const [llmStatus, setLlmStatus] = useState<{
        brain: string
        configured: boolean
        model: string | null
        bridge_injected: boolean
        bridge_stats: Record<string, unknown>
    } | null>(null)
    const [testInput, setTestInput] = useState('')
    const [testResult, setTestResult] = useState<{ response: string; latency: number } | null>(null)
    const [testing, setTesting] = useState(false)

    const [mcpServerList, setMcpServerList] = useState<McpServerItem[]>([])
    const [agentList, setAgentList] = useState<AgentItem[]>([])
    const [skillList, setSkillList] = useState<SkillItem[]>([])
    const [dynamicLoading, setDynamicLoading] = useState(true)
    // [FIX-FAB-005] 替换硬编码系统统计: 改为聚合真实API数据
    const [systemStats, setSystemStats] = useState<{
        mcpCount: number
        agentCount: number
        agentL1: number
        agentL2: number
        agentL3: number
        skillCount: number
        apiEndpoints: number
        memoryLayers: number
    } | null>(null)

    // ✅ DeepSeek V4-Pro/V4-Flash 配置状态
    const [deepseekConfig, setDeepseekConfig] = useState<DeepSeekConfig>(() => {
        const stored = loadDeepSeekConfigFromStorage()
        return { ...DEFAULT_DEEPSEEK_CONFIG, ...stored }
    })
    const [deepseekLoading, setDeepseekLoading] = useState(false)
    const [deepseekSaving, setDeepseekSaving] = useState(false)
    const [apiKeyModalOpen, setApiKeyModalOpen] = useState(false)
    const [newApiKey, setNewApiKey] = useState('')
    const [systemPromptModalOpen, setSystemPromptModalOpen] = useState(false)
    const [systemPromptViewOpen, setSystemPromptViewOpen] = useState(false)
    const [editingSystemPrompt, setEditingSystemPrompt] = useState('')
    const [testingConnection, setTestingConnection] = useState(false)

    const MCP_ICON_MAP: Record<string, React.ReactNode> = {
        'tianji-native': <DatabaseOutlined />,
        'agent-framework-global': <RobotOutlined />,
        'memory-engine-global': <DatabaseOutlined />,
        'command-executor': <ThunderboltOutlined />,
        'ops-engine': <FileTextOutlined />,
        'security-scanner': <CheckCircleOutlined />,
        'performance-profiler': <BulbOutlined />,
    }

    const MCP_COLOR_MAP: Record<string, string> = {
        'tianji-native': '#eb2f96',
        'agent-framework-global': '#722ed1',
        'memory-engine-global': '#1890ff',
        'command-executor': '#52c41a',
        'ops-engine': '#fa8c16',
        'security-scanner': '#f5222d',
        'performance-profiler': '#13c2c2',
    }

    const fetchDynamicLists = async () => {
        try {
            const [mcpRes, agentsRes, skillsRes] = await Promise.allSettled([
                api.get('/api/mcp/'),
                api.get('/api/orchestrator/agents'),
                api.get('/api/skills'),
            ])

            if (mcpRes.status === 'fulfilled') {
                const mcpData = mcpRes.value
                const servers = mcpData?.servers || mcpData || []
                if (Array.isArray(servers)) {
                    setMcpServerList(
                        servers.map((s: any) => ({
                            key: s.key || s.name,
                            name: s.name || s.key,
                            role: s.role || s.description || '',
                            exe: s.exe || s.executable || '',
                            enabled: s.enabled !== false,
                            env: s.env || s.environment || {},
                        }))
                    )
                }
            }

            if (agentsRes.status === 'fulfilled') {
                const agentsData = agentsRes.value
                const agents = agentsData?.agents || agentsData || []
                if (Array.isArray(agents)) {
                    setAgentList(
                        agents.map((a: any) => ({
                            name: a.name || a.id || '',
                            role: a.role || a.level || '',
                            description: a.description || a.desc || '',
                            enabled: a.enabled !== false,
                            priority: a.priority,
                        }))
                    )
                }
            }

            // 加载Skills配置列表
            if (skillsRes.status === 'fulfilled') {
                const skillsData = skillsRes.value
                const skills = skillsData?.skills || []
                if (Array.isArray(skills)) {
                    setSkillList(
                        skills.map((s: any) => ({
                            name: s.name || s.id || '',
                            description: s.description || '',
                            layer: s.layer || 'episodic',
                        }))
                    )
                }
            }

            // [FIX-FAB-005] 聚合真实统计数据 (替换硬编码的"Web端口8771/MCP=6/API=71/Agent=19..."等)
            try {
                const [mcpServersRes, agentsResData, skillsResData, memStatsRes, openapiRes] = await Promise.allSettled([
                    api.get('/api/mcp/servers'),
                    Promise.resolve(agentsRes.status === 'fulfilled' ? agentsRes.value : null),
                    Promise.resolve(skillsRes.status === 'fulfilled' ? skillsRes.value : null),
                    api.get('/api/memory/stats'),
                    api.get('/openapi.json'),
                ])

                const mcpServersList: any[] = mcpServersRes.status === 'fulfilled'
                    ? ((mcpServersRes.value as any)?.servers || [])
                    : []
                const agentsRaw: any[] = agentsResData.status === 'fulfilled'
                    ? ((agentsResData.value as any)?.agents || (agentsResData.value as any) || [])
                    : []
                const skillsRaw: any[] = skillsResData.status === 'fulfilled'
                    ? ((skillsResData.value as any)?.skills || [])
                    : []
                const memStats: any = memStatsRes.status === 'fulfilled' ? (memStatsRes.value as any) : null
                const openapi: any = openapiRes.status === 'fulfilled' ? (openapiRes.value as any) : null

                // Agent 分层统计 (L1守护/L2执行/L3决策)
                const l1 = agentsRaw.filter((a: any) => /L1|守护|guard/i.test(a.level || a.role || '')).length
                const l2 = agentsRaw.filter((a: any) => /L2|执行|exec/i.test(a.level || a.role || '')).length
                const l3 = agentsRaw.filter((a: any) => /L3|决策|decision/i.test(a.level || a.role || '')).length

                setSystemStats({
                    mcpCount: mcpServersList.length,
                    agentCount: agentsRaw.length,
                    agentL1: l1,
                    agentL2: l2,
                    agentL3: l3,
                    skillCount: skillsRaw.length,
                    apiEndpoints: openapi?.paths ? Object.keys(openapi.paths).length : 0,
                    memoryLayers: memStats?.layers ? Object.keys(memStats.layers).length : 6,
                })
            } catch {
                // 聚合统计失败不影响主流程
            }
        } catch {
            // 静默降级，不影响其他功能
        } finally {
            setDynamicLoading(false)
        }
    }

    useEffect(() => {
        fetchConfig()
        fetchLlmStatus()
        fetchDynamicLists()
        fetchDeepSeekConfig()
    }, [])

    // ✅ DeepSeek: 获取配置
    const fetchDeepSeekConfig = async () => {
        setDeepseekLoading(true)
        try {
            const [promptRes, rulesRes] = await Promise.allSettled([
                api.get('/api/deepseek/system-prompt'),
                api.get('/api/deepseek/rules'),
            ])

            const newConfig: DeepSeekConfig = { ...deepseekConfig }

            if (promptRes.status === 'fulfilled') {
                const promptData = promptRes.value
                const data = promptData?.data ?? promptData
                if (data) {
                    newConfig.systemPrompt = data.system_prompt || data.prompt || ''
                    newConfig.apiKey = data.api_key || ''
                    newConfig.apiKeyMasked = maskApiKey(data.api_key || '')
                    newConfig.defaultMode = (data.default_mode as DeepSeekModelMode) || newConfig.defaultMode
                    newConfig.thinkingEnabled = data.thinking_enabled ?? newConfig.thinkingEnabled
                    newConfig.reasoningEffort = (data.reasoning_effort as DeepSeekReasoningEffort) || newConfig.reasoningEffort
                    newConfig.useLawPrompt = data.use_law_prompt ?? newConfig.useLawPrompt
                }
            }

            if (rulesRes.status === 'fulfilled') {
                const rulesData = rulesRes.value
                const data = rulesData?.data ?? rulesRes
                if (data?.rules && Array.isArray(data.rules)) {
                    newConfig.lawRules = data.rules.map((r: any) => ({
                        id: r.id || r.name || '',
                        name: r.name || r.title || '',
                        description: r.description || r.desc || '',
                    }))
                }
            }

            setDeepseekConfig(newConfig)
            saveDeepSeekConfigToStorage({
                defaultMode: newConfig.defaultMode,
                thinkingEnabled: newConfig.thinkingEnabled,
                reasoningEffort: newConfig.reasoningEffort,
                useLawPrompt: newConfig.useLawPrompt,
            })
        } catch {
            // 降级: 使用本地存储的配置
            message.warning('DeepSeek配置获取失败，使用本地缓存')
        } finally {
            setDeepseekLoading(false)
        }
    }

    // ✅ DeepSeek: 保存配置
    const saveDeepSeekConfig = async (updates?: Partial<DeepSeekConfig>) => {
        setDeepseekSaving(true)
        try {
            const configToSave = updates ? { ...deepseekConfig, ...updates } : deepseekConfig
            const res = await api.post('/api/deepseek/system-prompt', {
                system_prompt: configToSave.systemPrompt,
                default_mode: configToSave.defaultMode,
                thinking_enabled: configToSave.thinkingEnabled,
                reasoning_effort: configToSave.reasoningEffort,
                use_law_prompt: configToSave.useLawPrompt,
                api_key: configToSave.apiKey || undefined,
            })
            const data = res?.data ?? res
            if (data?.success !== false) {
                message.success('DeepSeek配置保存成功')
                setDeepseekConfig(configToSave)
                saveDeepSeekConfigToStorage({
                    defaultMode: configToSave.defaultMode,
                    thinkingEnabled: configToSave.thinkingEnabled,
                    reasoningEffort: configToSave.reasoningEffort,
                    useLawPrompt: configToSave.useLawPrompt,
                })
            }
        } catch {
            message.error('DeepSeek配置保存失败')
        } finally {
            setDeepseekSaving(false)
        }
    }

    // ✅ DeepSeek: 测试连接
    const testDeepSeekConnection = async () => {
        setTestingConnection(true)
        try {
            const res = await api.post('/api/llm/classify', { content: '测试连接' })
            const data = res?.data ?? res
            if (data) {
                message.success('DeepSeek连接测试成功')
            }
        } catch (err: unknown) {
            const errorMsg = err instanceof Error ? err.message : '连接失败'
            message.error(`DeepSeek连接测试失败: ${errorMsg}`)
        } finally {
            setTestingConnection(false)
        }
    }

    // ✅ DeepSeek: 修改API密钥
    const handleSaveApiKey = async () => {
        if (!newApiKey.trim()) {
            message.warning('请输入API密钥')
            return
        }
        const updated = {
            ...deepseekConfig,
            apiKey: newApiKey.trim(),
            apiKeyMasked: maskApiKey(newApiKey.trim()),
        }
        setDeepseekConfig(updated)
        setApiKeyModalOpen(false)
        setNewApiKey('')
        await saveDeepSeekConfig({ apiKey: updated.apiKey })
    }

    // ✅ DeepSeek: 保存系统提示词
    const handleSaveSystemPrompt = async () => {
        const updated = { ...deepseekConfig, systemPrompt: editingSystemPrompt }
        setDeepseekConfig(updated)
        setSystemPromptModalOpen(false)
        await saveDeepSeekConfig({ systemPrompt: editingSystemPrompt })
    }

    const DEFAULT_LAYERS = {
        sensory: { max_size: 1000, retention_hours: 1 },
        working: { max_size: 5000, retention_hours: 4 },
        short_term: { max_size: 10000, retention_hours: 24 },
        episodic: { max_size: 50000, retention_hours: 720 },
        semantic: { max_size: 100000, retention_hours: 8760 },
        meta: { max_size: 20000, retention_hours: 8760 },
    }

    const DEFAULT_LLM: LlmConfig = {
        temperature: 0.7,
        max_tokens: 2000,
        top_p: 0.9,
        features: {
            classify: true,
            auto_tag: true,
            summarize: true,
            extract_knowledge: false,
        },
    }

    const DEFAULT_CONFIG: ConfigData = {
        memory: {
            auto_capture_enabled: true,
            layers: DEFAULT_LAYERS,
            backup_interval_minutes: 30,
            max_backup_count: 12,
        },
        api: { base_url: 'http://localhost:8771', timeout_ms: 30000, max_retries: 3 },
        monitoring: {
            stats_interval_seconds: 8,
            health_check_interval_seconds: 60,
            history_retention_hours: 24,
        },
        llm: DEFAULT_LLM,
    }

    const mergeConfig = (apiData: any): ConfigData => {
        if (!apiData) return DEFAULT_CONFIG
        const merged = { ...DEFAULT_CONFIG }
        if (apiData.memory) {
            merged.memory = {
                ...(merged.memory ?? DEFAULT_CONFIG.memory),
                ...apiData.memory,
                layers: {
                    ...(DEFAULT_LAYERS as Record<string, { max_size: number; retention_hours: number }>),
                    ...(apiData.memory.layers || {}),
                },
            }
        }
        if (apiData.api) merged.api = { ...merged.api, ...apiData.api }
        if (apiData.monitoring) merged.monitoring = { ...merged.monitoring, ...apiData.monitoring }
        if (apiData.llm) {
            merged.llm = { ...DEFAULT_LLM, ...apiData.llm }
            if (apiData.llm.features && merged.llm) {
                merged.llm.features = { ...DEFAULT_LLM.features, ...apiData.llm.features }
            }
        }
        return merged
    }

    const fetchConfig = async () => {
        try {
            setLoading(true)
            const res = await api.get('/api/config')
            const merged = mergeConfig(res)
            setConfig(merged)
            form.setFieldsValue(merged)
            setError(null)
        } catch {
            setError('无法连接配置服务，使用本地默认配置')
            setConfig(DEFAULT_CONFIG)
            form.setFieldsValue(DEFAULT_CONFIG)
        } finally {
            setLoading(false)
        }
    }

    const handleSave = async () => {
        try {
            setSaving(true)
            let values: Record<string, any> = {}
            try {
                values = await form.validateFields()
            } catch {
                values = form.getFieldsValue()
            }
            if (config?.llm) {
                values.llm = { ...config.llm }
            }

            // [FIX-TS-013] 删除未使用的 saveRes (不需要返回值)
            await api.post('/api/config', values)
            message.success('配置保存成功')
            setConfig(values)

            let reloadMsg = ''
            try {
                const reloadRes = await api.post('/api/llm/reload')
                if (reloadRes?.success) {
                    reloadMsg = reloadRes.message || 'LLM重载成功'
                } else if (reloadRes?.message) {
                    reloadMsg = `LLM: ${reloadRes.message}`
                }
            } catch (reloadErr: unknown) {
                const reloadError = reloadErr as {
                    response?: { status?: number; data?: { detail?: string } }
                }
                if (reloadError.response?.status === 404) {
                    reloadMsg = 'LLM重载端点不可用（需重启服务）'
                } else if (reloadError.response?.data?.detail) {
                    reloadMsg = `LLM重载失败: ${reloadError.response.data.detail.substring(0, 50)}`
                } else {
                    reloadMsg = 'LLM重载跳过（非致命错误）'
                }
            }

            if (reloadMsg && !reloadMsg.includes('成功')) {
                message.warning(reloadMsg)
            }

            fetchLlmStatus()
        } catch (err: unknown) {
            const error = err as {
                response?: { status?: number; data?: { detail?: string } }
                message?: string
            }
            if (error.response?.status === 0 || !error.response) {
                message.error('网络连接失败，请检查后端服务是否运行在 http://127.0.0.1:8771')
            } else if (error.response?.status === 404) {
                message.error('API端点不存在，请确认后端版本兼容')
            } else if ((error.response?.status ?? 0) >= 500) {
                // [FIX-TS-020] 修复 possibly undefined: status 可能 undefined, 使用 ?? 0
                message.error(`服务器内部错误 (${error.response?.status ?? 'unknown'})`)
            } else {
                const detail = error.response?.data?.detail || error.message || '未知错误'
                message.warning(`配置部分保存: ${detail.substring(0, 80)}`)
            }

            try {
                const values = form.getFieldsValue()
                if (config?.llm) {
                    values.llm = { ...config.llm }
                }
                setConfig(values)
            } catch {
                // ignore
            }
        } finally {
            setSaving(false)
        }
    }

    const fetchLlmStatus = async () => {
        try {
            const status = await api.get('/api/llm/status')
            setLlmStatus(status)
        } catch {
            setLlmStatus({
                brain: 'deepseek',
                configured: false,
                model: null,
                bridge_injected: false,
                bridge_stats: {},
            })
        }
    }

    const handleTestLlm = async () => {
        if (!testInput.trim()) {
            message.warning('请输入测试内容')
            return
        }
        setTesting(true)
        setTestResult(null)
        const startTime = Date.now()
        try {
            const res = await api.post('/api/llm/classify', { content: testInput })
            const latency = Date.now() - startTime
            setTestResult({ response: JSON.stringify(res, null, 2), latency })
            message.success(`测试成功，响应时间 ${latency}ms`)
        } catch (err: unknown) {
            const latency = Date.now() - startTime
            const errorMsg = err instanceof Error ? err.message : '测试失败'
            setTestResult({ response: `错误: ${errorMsg}`, latency })
            message.error('DeepSeek连接测试失败')
        } finally {
            setTesting(false)
        }
    }

    const handleFeatureToggle = (feature: keyof NonNullable<LlmConfig['features']>, checked: boolean) => {
        if (!config?.llm) return
        const updated = { ...config }
        // [FIX-TS-021] 修复 possibly undefined: 使用非空断言或默认值
        updated.llm = {
            ...updated.llm!,
            features: { ...updated.llm?.features, [feature]: checked } as NonNullable<LlmConfig['features']>,
        }
        setConfig(updated)
    }

    if (loading) {
        return (
            <div style={{ textAlign: 'center', padding: '80px 0' }}>
                <Spin size="large">
                    <div>加载系统配置...</div>
                </Spin>
            </div>
        )
    }

    const renderMemoryConfig = () => (
        <div>
            <Card
                size="small"
                title={
                    <Space>
                        <DatabaseOutlined style={{ color: '#1890ff' }} />
                        <span>ICME六层记忆配置</span>
                    </Space>
                }
            >
                <Row gutter={[16, 16]}>
                    {config?.memory?.layers ? (
                        Object.entries(config.memory.layers).map(([layer, cfg]) => (
                            <Col xs={24} sm={12} lg={8} key={layer}>
                                <Card size="small" type="inner" title={LAYER_NAMES[layer] || layer}>
                                    <Descriptions column={1} size="small">
                                        <Descriptions.Item label="最大容量">
                                            <InputNumber
                                                style={{ width: '100%' }}
                                                value={cfg.max_size}
                                                onChange={(val) => {
                                                    const updated = { ...config }
                                                    if (updated.memory?.layers[layer]) {
                                                        updated.memory.layers[layer].max_size = val ?? 0
                                                        setConfig(updated)
                                                    }
                                                }}
                                                min={100}
                                                max={10000000}
                                                step={100}
                                            />
                                        </Descriptions.Item>
                                        <Descriptions.Item label="保留时长(小时)">
                                            <InputNumber
                                                style={{ width: '100%' }}
                                                value={cfg.retention_hours}
                                                onChange={(val) => {
                                                    const updated = { ...config }
                                                    if (updated.memory?.layers[layer]) {
                                                        updated.memory.layers[layer].retention_hours = val ?? 0
                                                        setConfig(updated)
                                                    }
                                                }}
                                                min={1}
                                                max={87600}
                                                step={1}
                                            />
                                        </Descriptions.Item>
                                    </Descriptions>
                                </Card>
                            </Col>
                        ))
                    ) : (
                        <Col span={24}>
                            <Empty description="ICME六层记忆配置加载中..." />
                        </Col>
                    )}
                </Row>
            </Card>

            <Card size="small" title="记忆全局设置" style={{ marginTop: 16 }}>
                <Row gutter={[16, 16]}>
                    <Col xs={24} sm={12} lg={6}>
                        <Form.Item
                            label="自动捕获"
                            name={['memory', 'auto_capture_enabled']}
                            valuePropName="checked"
                        >
                            <Switch checkedChildren="开启" unCheckedChildren="关闭" />
                        </Form.Item>
                    </Col>
                    <Col xs={24} sm={12} lg={6}>
                        <Form.Item label="备份间隔(分钟)" name={['memory', 'backup_interval_minutes']}>
                            <InputNumber min={5} max={1440} style={{ width: '100%' }} />
                        </Form.Item>
                    </Col>
                    <Col xs={24} sm={12} lg={6}>
                        <Form.Item label="最大备份数" name={['memory', 'max_backup_count']}>
                            <InputNumber min={1} max={100} style={{ width: '100%' }} />
                        </Form.Item>
                    </Col>
                </Row>
            </Card>
        </div>
    )

    const renderMcpConfig = () => (
        <div>
            <Card
                size="small"
                title={
                    <Space>
                        <ApiOutlined style={{ color: '#722ed1' }} />
                        <span>
                            MCP Server配置 ({dynamicLoading ? '检测中...' : `${mcpServerList.length}服务器`})
                        </span>
                    </Space>
                }
            >
                {mcpServerList.length === 0 && !dynamicLoading ? (
                    <Empty description="MCP服务器数据未获取（后端 /api/mcp 不可用）" />
                ) : (
                    <Row gutter={[16, 16]}>
                        {mcpServerList.map((server) => {
                            const icon = MCP_ICON_MAP[server.key] || <ApiOutlined />
                            const color = MCP_COLOR_MAP[server.key] || '#1890ff'
                            return (
                                <Col xs={24} sm={12} lg={8} key={server.key}>
                                    <Card
                                        size="small"
                                        hoverable
                                        title={
                                            <Space>
                                                <span style={{ color }}>{icon}</span>
                                                <Text strong>{server.name}</Text>
                                            </Space>
                                        }
                                        extra={
                                            <Switch
                                                size="small"
                                                checkedChildren="ON"
                                                unCheckedChildren="OFF"
                                                defaultChecked={server.enabled}
                                            />
                                        }
                                    >
                                        <Descriptions column={1} size="small">
                                            <Descriptions.Item label="标识符">
                                                <Tag color="blue">{server.key}</Tag>
                                            </Descriptions.Item>
                                            <Descriptions.Item label="角色">{server.role}</Descriptions.Item>
                                            <Descriptions.Item label="可执行文件">
                                                <Text code style={{ fontSize: 11 }}>
                                                    {server.exe}
                                                </Text>
                                            </Descriptions.Item>
                                            <Descriptions.Item label="环境变量">
                                                {Object.entries(server.env).map(([k, v]) => (
                                                    <Tag key={k} color="default" style={{ fontSize: 10, marginBottom: 2 }}>
                                                        {k}={v?.toString().slice(0, 30)}
                                                    </Tag>
                                                ))}
                                            </Descriptions.Item>
                                        </Descriptions>
                                    </Card>
                                </Col>
                            )
                        })}
                    </Row>
                )}
            </Card>
        </div>
    )

    const renderAgentConfig = () => {
        const l1Count = agentList.filter((a) => a.role?.startsWith('L1')).length
        const l2Count = agentList.filter((a) => a.role?.startsWith('L2')).length
        const l3Count = agentList.filter((a) => a.role?.startsWith('L3')).length

        return (
            <div>
                <Card
                    size="small"
                    title={
                        <Space>
                            <RobotOutlined style={{ color: '#52c41a' }} />
                            <span>
                                Agent配置 ({dynamicLoading ? '检测中...' : `${agentList.length}Agent·L1-L3三层`})
                            </span>
                        </Space>
                    }
                >
                    {agentList.length === 0 && !dynamicLoading ? (
                        <Empty description="Agent数据未获取（后端 /api/orchestrator/agents 不可用）" />
                    ) : (
                        <Table
                            dataSource={agentList.map((a, i) => ({ ...a, key: i }))}
                            columns={[
                                {
                                    title: 'Agent名称',
                                    dataIndex: 'name',
                                    key: 'name',
                                    render: (text: string) => <Text strong>{text}</Text>,
                                    width: 200,
                                },
                                {
                                    title: '层级/角色',
                                    dataIndex: 'role',
                                    key: 'role',
                                    render: (role: string) => {
                                        const level = role.startsWith('L1')
                                            ? 'purple'
                                            : role.startsWith('L2')
                                                ? 'blue'
                                                : 'gold'
                                        return <Tag color={level}>{role}</Tag>
                                    },
                                    width: 160,
                                },
                                {
                                    title: '描述',
                                    dataIndex: 'description',
                                    key: 'description',
                                    render: (desc: string) => <Text type="secondary">{desc}</Text>,
                                },
                                {
                                    title: '状态',
                                    key: 'status',
                                    render: (_: any, record: AgentItem) => (
                                        <Badge
                                            status={record.enabled !== false ? 'success' : 'warning'}
                                            text={record.enabled !== false ? '已注册' : '待激活'}
                                        />
                                    ),
                                    width: 100,
                                },
                            ]}
                            size="small"
                            pagination={{ pageSize: 10, showSizeChanger: false }}
                            title={() => (
                                <Space>
                                    <span>Agent注册表</span>
                                    <Tag color="purple">L1: {l1Count}</Tag>
                                    <Tag color="blue">L2: {l2Count}</Tag>
                                    <Tag color="gold">L3: {l3Count}</Tag>
                                </Space>
                            )}
                        />
                    )}
                </Card>
            </div>
        )
    }

    const renderSkillConfig = () => (
        <div>
            <Card
                size="small"
                title={
                    <Space>
                        <FileTextOutlined style={{ color: '#fa8c16' }} />
                        <span>Skills配置 ({dynamicLoading ? '检测中...' : `${skillList.length}技能`})</span>
                    </Space>
                }
            >
                <Table
                    dataSource={skillList.map((s, i) => ({ ...s, key: i }))}
                    columns={[
                        {
                            title: '技能名称',
                            dataIndex: 'name',
                            key: 'name',
                            render: (text: string) => <Text code>{text}</Text>,
                            width: 240,
                        },
                        {
                            title: '描述',
                            dataIndex: 'description',
                            key: 'description',
                            render: (desc: string) => <Text type="secondary">{desc}</Text>,
                        },
                        {
                            title: '所属记忆层',
                            dataIndex: 'layer',
                            key: 'layer',
                            render: (layer: string) => (
                                <Tag
                                    color={
                                        layer === 'sensory'
                                            ? 'gold'
                                            : layer === 'working'
                                                ? 'blue'
                                                : layer === 'episodic'
                                                    ? 'pink'
                                                    : layer === 'semantic'
                                                        ? 'purple'
                                                        : layer === 'meta'
                                                            ? 'orange'
                                                            : 'default'
                                    }
                                >
                                    {LAYER_NAMES[layer] || layer}
                                </Tag>
                            ),
                            width: 130,
                        },
                    ]}
                    size="small"
                    pagination={false}
                />
            </Card>
        </div>
    )

    const renderDeepSeekConfig = () => (
        <div>
            <Card
                size="small"
                title={
                    <Space>
                        <BulbOutlined style={{ color: '#f5a623' }} />
                        <span>DeepSeek大脑 · 连接状态</span>
                    </Space>
                }
            >
                <Row gutter={[16, 16]}>
                    <Col xs={24} sm={12} lg={6}>
                        <Descriptions column={1} size="small" bordered>
                            <Descriptions.Item label="引擎类型">
                                <Tag color="orange">{llmStatus?.brain ?? 'deepseek'}</Tag>
                            </Descriptions.Item>
                            <Descriptions.Item label="API状态">
                                {llmStatus?.configured ? (
                                    <Tag color="success" icon={<CheckCircleOutlined />}>
                                        已连接
                                    </Tag>
                                ) : (
                                    <Tag color="error" icon={<CloseCircleOutlined />}>
                                        未配置/不可用
                                    </Tag>
                                )}
                            </Descriptions.Item>
                        </Descriptions>
                    </Col>
                    <Col xs={24} sm={12} lg={6}>
                        <Descriptions column={1} size="small" bordered>
                            <Descriptions.Item label="模型名称">
                                <Text code>{llmStatus?.model ?? 'deepseek-chat'}</Text>
                            </Descriptions.Item>
                            <Descriptions.Item label="注入状态">
                                {llmStatus?.bridge_injected ? (
                                    <Tag color="success">remember/recall 已注入</Tag>
                                ) : (
                                    <Tag color="default">未注入</Tag>
                                )}
                            </Descriptions.Item>
                        </Descriptions>
                    </Col>
                    <Col xs={24} sm={12} lg={6}>
                        <Descriptions column={1} size="small" bordered>
                            <Descriptions.Item label="桥接统计">
                                {llmStatus?.bridge_stats && Object.keys(llmStatus.bridge_stats).length > 0 ? (
                                    Object.entries(llmStatus.bridge_stats).map(([k, v]) => (
                                        <Tag key={k} color="blue" style={{ marginBottom: 2 }}>
                                            {k}: {String(v)}
                                        </Tag>
                                    ))
                                ) : (
                                    <Text type="secondary">暂无数据</Text>
                                )}
                            </Descriptions.Item>
                        </Descriptions>
                    </Col>
                    <Col xs={24} sm={12} lg={6}>
                        <Button
                            size="small"
                            icon={<ReloadOutlined />}
                            onClick={fetchLlmStatus}
                            style={{ marginTop: 4 }}
                        >
                            刷新状态
                        </Button>
                    </Col>
                </Row>
            </Card>

            <Card size="small" title="API密钥配置" style={{ marginTop: 16 }}>
                <Row gutter={[24, 16]}>
                    <Col xs={24} sm={16}>
                        <Form.Item
                            label="DeepSeek API Key"
                            tooltip="从 https://platform.deepseek.com 获取API密钥，保存后立即生效"
                            name={['llm', 'api_key']}
                        >
                            <Input.Password
                                placeholder="sk-xxxxxxxxxxxxxxxxxxxxxxxx"
                                value={config?.llm?.api_key ?? ''}
                                onChange={(e) => {
                                    const updated = { ...config }
                                    if (updated.llm) {
                                        updated.llm = { ...updated.llm, api_key: e.target.value }
                                    } else {
                                        updated.llm = {
                                            api_key: e.target.value,
                                            temperature: 0.7,
                                            max_tokens: 2000,
                                            top_p: 0.9,
                                            features: {
                                                classify: true,
                                                auto_tag: true,
                                                summarize: true,
                                                extract_knowledge: false,
                                            },
                                        }
                                    }
                                    setConfig(updated)
                                }}
                                visibilityToggle
                            />
                        </Form.Item>
                    </Col>
                    <Col xs={24} sm={8}>
                        <Form.Item label="Base URL" name={['llm', 'base_url']}>
                            <Input
                                placeholder="https://api.deepseek.com/v1"
                                value={config?.llm?.base_url ?? 'https://api.deepseek.com/v1'}
                                onChange={(e) => {
                                    const updated = { ...config }
                                    if (updated.llm) {
                                        updated.llm = { ...updated.llm, base_url: e.target.value }
                                    } else {
                                        updated.llm = {
                                            base_url: e.target.value,
                                            temperature: 0.7,
                                            max_tokens: 2000,
                                            top_p: 0.9,
                                            // [FIX-TS-021] 添加必需的 features 字段
                                            features: {
                                                classify: true,
                                                auto_tag: true,
                                                summarize: true,
                                                extract_knowledge: true,
                                            },
                                        }
                                    }
                                    setConfig(updated)
                                }}
                            />
                        </Form.Item>
                    </Col>
                </Row>
                <Row>
                    <Col>
                        <Space>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                                当前状态:{' '}
                                {llmStatus?.configured ? (
                                    <Tag color="success" icon={<CheckCircleOutlined />}>
                                        密钥已配置
                                    </Tag>
                                ) : (
                                    <Tag color="error" icon={<CloseCircleOutlined />}>
                                        未配置密钥
                                    </Tag>
                                )}
                            </Text>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                                保存配置后需重启服务生效，或通过 /api/llm/reload 热加载
                            </Text>
                        </Space>
                    </Col>
                </Row>
            </Card>

            <Card size="small" title="模型参数配置" style={{ marginTop: 16 }}>
                <Row gutter={[24, 16]}>
                    <Col xs={24} sm={12} lg={8}>
                        <Form.Item label="Temperature (0.0-2.0)" name={['llm', 'temperature']}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                <Slider
                                    min={0}
                                    max={2}
                                    step={0.1}
                                    value={config?.llm?.temperature ?? 0.7}
                                    onChange={(val) => {
                                        const updated = { ...config }
                                        if (updated.llm) {
                                            updated.llm = { ...updated.llm, temperature: val }
                                            setConfig(updated)
                                        }
                                    }}
                                    style={{ flex: 1 }}
                                />
                                <InputNumber
                                    min={0}
                                    max={2}
                                    step={0.1}
                                    value={config?.llm?.temperature ?? 0.7}
                                    onChange={(val) => {
                                        const updated = { ...config }
                                        if (updated.llm) {
                                            updated.llm = { ...updated.llm, temperature: val ?? 0.7 }
                                            setConfig(updated)
                                        }
                                    }}
                                    width={70}
                                />
                            </div>
                        </Form.Item>
                    </Col>
                    <Col xs={24} sm={12} lg={8}>
                        <Form.Item label="Max Tokens (100-8000)" name={['llm', 'max_tokens']}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                <Slider
                                    min={100}
                                    max={8000}
                                    step={100}
                                    value={config?.llm?.max_tokens ?? 2000}
                                    onChange={(val) => {
                                        const updated = { ...config }
                                        if (updated.llm) {
                                            updated.llm = { ...updated.llm, max_tokens: val }
                                            setConfig(updated)
                                        }
                                    }}
                                    style={{ flex: 1 }}
                                />
                                <InputNumber
                                    min={100}
                                    max={8000}
                                    step={100}
                                    value={config?.llm?.max_tokens ?? 2000}
                                    onChange={(val) => {
                                        const updated = { ...config }
                                        if (updated.llm) {
                                            updated.llm = { ...updated.llm, max_tokens: val ?? 2000 }
                                            setConfig(updated)
                                        }
                                    }}
                                    width={90}
                                />
                            </div>
                        </Form.Item>
                    </Col>
                    <Col xs={24} sm={12} lg={8}>
                        <Form.Item label="Top P (0.0-1.0)" name={['llm', 'top_p']}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                <Slider
                                    min={0}
                                    max={1}
                                    step={0.05}
                                    value={config?.llm?.top_p ?? 0.9}
                                    onChange={(val) => {
                                        const updated = { ...config }
                                        if (updated.llm) {
                                            updated.llm = { ...updated.llm, top_p: val }
                                            setConfig(updated)
                                        }
                                    }}
                                    style={{ flex: 1 }}
                                />
                                <InputNumber
                                    min={0}
                                    max={1}
                                    step={0.05}
                                    value={config?.llm?.top_p ?? 0.9}
                                    onChange={(val) => {
                                        const updated = { ...config }
                                        if (updated.llm) {
                                            updated.llm = { ...updated.llm, top_p: val ?? 0.9 }
                                            setConfig(updated)
                                        }
                                    }}
                                    width={65}
                                />
                            </div>
                        </Form.Item>
                    </Col>
                </Row>
            </Card>

            <Card size="small" title="DeepSeek功能开关" style={{ marginTop: 16 }}>
                <Row gutter={[16, 16]}>
                    <Col xs={24} sm={12} lg={6}>
                        <Form.Item label="自动分类 (tianji_classify)" tooltip="自动分析内容并推荐存储层级">
                            <Switch
                                checkedChildren="开启"
                                unCheckedChildren="关闭"
                                checked={config?.llm?.features?.classify ?? true}
                                onChange={(checked) => handleFeatureToggle('classify', checked)}
                            />
                        </Form.Item>
                    </Col>
                    <Col xs={24} sm={12} lg={6}>
                        <Form.Item label="自动标签 (tianji_auto_tag)" tooltip="自动为记忆条目生成语义标签">
                            <Switch
                                checkedChildren="开启"
                                unCheckedChildren="关闭"
                                checked={config?.llm?.features?.auto_tag ?? true}
                                onChange={(checked) => handleFeatureToggle('auto_tag', checked)}
                            />
                        </Form.Item>
                    </Col>
                    <Col xs={24} sm={12} lg={6}>
                        <Form.Item label="自动摘要 (tianji_summarize)" tooltip="自动生成记忆内容的摘要">
                            <Switch
                                checkedChildren="开启"
                                unCheckedChildren="关闭"
                                checked={config?.llm?.features?.summarize ?? true}
                                onChange={(checked) => handleFeatureToggle('summarize', checked)}
                            />
                        </Form.Item>
                    </Col>
                    <Col xs={24} sm={12} lg={6}>
                        <Form.Item label="知识提取 (tianji_extract_knowledge)" tooltip="从内容中提取知识三元组">
                            <Switch
                                checkedChildren="开启"
                                unCheckedChildren="关闭"
                                checked={config?.llm?.features?.extract_knowledge ?? false}
                                onChange={(checked) => handleFeatureToggle('extract_knowledge', checked)}
                            />
                        </Form.Item>
                    </Col>
                </Row>
            </Card>

            <Card size="small" title="实时测试区域" style={{ marginTop: 16 }}>
                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                    <Space.Compact style={{ width: '100%' }}>
                        <Input
                            placeholder="输入测试文本，调用 DeepSeek classify 接口验证连通性..."
                            value={testInput}
                            onChange={(e) => setTestInput(e.target.value)}
                            onPressEnter={handleTestLlm}
                            allowClear
                            style={{ flex: 1 }}
                        />
                        <Button
                            type="primary"
                            icon={<ThunderboltOutlined />}
                            onClick={handleTestLlm}
                            loading={testing}
                        >
                            测试连接
                        </Button>
                    </Space.Compact>
                    {testResult && (
                        <Alert
                            type={testResult.response.startsWith('错误') ? 'error' : 'success'}
                            message={`响应时间: ${testResult.latency}ms`}
                            description={
                                <pre
                                    style={{
                                        maxHeight: 200,
                                        overflow: 'auto',
                                        margin: 0,
                                        fontSize: 12,
                                        whiteSpace: 'pre-wrap',
                                    }}
                                >
                                    {testResult.response}
                                </pre>
                            }
                        />
                    )}
                </Space>
            </Card>

            {/* ✅ DeepSeek V4-Pro/V4-Flash 双模式配置 */}
            <Card
                size="small"
                title={
                    <Space>
                        <BulbOutlined style={{ color: '#f5a623' }} />
                        <span>V4-Pro / V4-Flash 双模式配置</span>
                        {deepseekLoading && <Spin size="small" />}
                    </Space>
                }
                style={{ marginTop: 16 }}
                extra={
                    <Space>
                        <Button
                            size="small"
                            icon={<ReloadOutlined />}
                            onClick={fetchDeepSeekConfig}
                            loading={deepseekLoading}
                        >
                            刷新
                        </Button>
                        <Button
                            type="primary"
                            size="small"
                            icon={<SaveOutlined />}
                            onClick={() => saveDeepSeekConfig()}
                            loading={deepseekSaving}
                        >
                            保存配置
                        </Button>
                    </Space>
                }
            >
                {/* API密钥管理 */}
                <Row gutter={[16, 16]} align="middle">
                    <Col xs={24} sm={12}>
                        <Descriptions column={1} size="small" bordered>
                            <Descriptions.Item label={<><KeyOutlined /> API密钥</>}>
                                <Space>
                                    <Text code>
                                        {deepseekConfig.apiKeyMasked || '未配置'}
                                    </Text>
                                    <Button
                                        size="small"
                                        icon={<EditOutlined />}
                                        onClick={() => {
                                            setNewApiKey(deepseekConfig.apiKey)
                                            setApiKeyModalOpen(true)
                                        }}
                                    >
                                        修改
                                    </Button>
                                    <Button
                                        size="small"
                                        icon={<ThunderboltOutlined />}
                                        onClick={testDeepSeekConnection}
                                        loading={testingConnection}
                                    >
                                        测试连接
                                    </Button>
                                </Space>
                            </Descriptions.Item>
                        </Descriptions>
                    </Col>
                    <Col xs={24} sm={12}>
                        <Alert
                            type="info"
                            showIcon
                            message="API密钥安全说明"
                            description="密钥仅在后端存储，前端显示脱敏。修改后立即生效，无需重启服务。"
                            style={{ fontSize: 12 }}
                        />
                    </Col>
                </Row>

                {/* 默认模式配置 */}
                <div style={{ marginTop: 16, padding: '12px 16px', background: 'rgba(245,158,11,0.04)', borderRadius: 6 }}>
                    <div style={{ marginBottom: 8, fontSize: 13, fontWeight: 500 }}>
                        <BulbOutlined style={{ color: '#f5a623' }} /> 默认对话模式
                    </div>
                    <Row gutter={[16, 16]} align="middle">
                        <Col xs={24} sm={12}>
                            <Space direction="vertical" style={{ width: '100%' }}>
                                <Segmented
                                    block
                                    value={deepseekConfig.defaultMode}
                                    onChange={(value: SegmentedValue) => {
                                        const newMode = value as DeepSeekModelMode
                                        setDeepseekConfig((prev) => ({
                                            ...prev,
                                            defaultMode: newMode,
                                            thinkingEnabled: newMode === 'v4-pro' ? prev.thinkingEnabled : false,
                                        }))
                                    }}
                                    options={[
                                        {
                                            label: (
                                                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                                                    <ThunderboltOutlined /> V4-Flash (高性价比)
                                                </span>
                                            ),
                                            value: 'v4-flash',
                                        },
                                        {
                                            label: (
                                                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                                                    <BulbOutlined /> V4-Pro (复杂推理)
                                                </span>
                                            ),
                                            value: 'v4-pro',
                                        },
                                    ]}
                                />
                                <Text type="secondary" style={{ fontSize: 11 }}>
                                    {deepseekConfig.defaultMode === 'v4-pro'
                                        ? 'V4-Pro: 适用于复杂推理、代码生成、数学计算等场景，支持Thinking模式'
                                        : 'V4-Flash: 响应速度更快，token消耗更低，适用于日常对话和简单任务'}
                                </Text>
                            </Space>
                        </Col>
                        <Col xs={24} sm={12}>
                            <Descriptions column={1} size="small">
                                <Descriptions.Item label="当前模式">
                                    <Tag color={deepseekConfig.defaultMode === 'v4-pro' ? 'orange' : 'green'}>
                                        {deepseekConfig.defaultMode === 'v4-pro' ? 'V4-Pro' : 'V4-Flash'}
                                    </Tag>
                                </Descriptions.Item>
                                <Descriptions.Item label="Thinking支持">
                                    {deepseekConfig.defaultMode === 'v4-pro' ? (
                                        <Tag color="purple">✅ 支持</Tag>
                                    ) : (
                                        <Tag>❌ 不支持</Tag>
                                    )}
                                </Descriptions.Item>
                            </Descriptions>
                        </Col>
                    </Row>
                </div>

                {/* Thinking模式默认配置 */}
                {deepseekConfig.defaultMode === 'v4-pro' && (
                    <div style={{ marginTop: 12, padding: '12px 16px', background: 'rgba(139,92,246,0.04)', borderRadius: 6 }}>
                        <div style={{ marginBottom: 8, fontSize: 13, fontWeight: 500 }}>
                            <SafetyOutlined style={{ color: '#8B5CF6' }} /> Thinking模式默认配置
                        </div>
                        <Row gutter={[16, 16]} align="middle">
                            <Col xs={24} sm={8}>
                                <Space>
                                    <Text>默认开启Thinking:</Text>
                                    <Switch
                                        checked={deepseekConfig.thinkingEnabled}
                                        onChange={(checked) =>
                                            setDeepseekConfig((prev) => ({ ...prev, thinkingEnabled: checked }))
                                        }
                                        checkedChildren="开启"
                                        unCheckedChildren="关闭"
                                    />
                                </Space>
                            </Col>
                            <Col xs={24} sm={16}>
                                {deepseekConfig.thinkingEnabled && (
                                    <Space>
                                        <Text>推理强度:</Text>
                                        <Segmented
                                            size="small"
                                            value={deepseekConfig.reasoningEffort}
                                            onChange={(value: SegmentedValue) =>
                                                setDeepseekConfig((prev) => ({
                                                    ...prev,
                                                    reasoningEffort: value as DeepSeekReasoningEffort,
                                                }))
                                            }
                                            options={[
                                                { label: 'Low (快速)', value: 'low' },
                                                { label: 'Medium (平衡)', value: 'medium' },
                                                { label: 'High (深度)', value: 'high' },
                                            ]}
                                        />
                                    </Space>
                                )}
                            </Col>
                        </Row>
                        {deepseekConfig.thinkingEnabled && (
                            <Alert
                                type="warning"
                                showIcon
                                message="Thinking模式将输出推理过程，消耗更多token"
                                description={`当前推理强度: ${deepseekConfig.reasoningEffort}。High模式token消耗约为Low模式的3-5倍。`}
                                style={{ marginTop: 8, fontSize: 12 }}
                            />
                        )}
                    </div>
                )}

                {/* 法则提示词配置 */}
                <div style={{ marginTop: 12, padding: '12px 16px', background: 'rgba(16,185,129,0.04)', borderRadius: 6 }}>
                    <div style={{ marginBottom: 8, fontSize: 13, fontWeight: 500 }}>
                        <SafetyOutlined style={{ color: '#10B981' }} /> 法则提示词注入配置
                    </div>
                    <Row gutter={[16, 16]} align="middle">
                        <Col xs={24} sm={8}>
                            <Space>
                                <Text>默认注入法则:</Text>
                                <Switch
                                    checked={deepseekConfig.useLawPrompt}
                                    onChange={(checked) =>
                                        setDeepseekConfig((prev) => ({ ...prev, useLawPrompt: checked }))
                                    }
                                    checkedChildren="注入"
                                    unCheckedChildren="关闭"
                                />
                                {deepseekConfig.useLawPrompt && (
                                    <Tag color="success" icon={<CheckCircleOutlined />}>
                                        已启用
                                    </Tag>
                                )}
                            </Space>
                        </Col>
                        <Col xs={24} sm={16}>
                            <Space>
                                <Button
                                    size="small"
                                    icon={<EyeOutlined />}
                                    onClick={() => setSystemPromptViewOpen(true)}
                                >
                                    查看系统提示词
                                </Button>
                                <Button
                                    size="small"
                                    icon={<EditOutlined />}
                                    onClick={() => {
                                        setEditingSystemPrompt(deepseekConfig.systemPrompt)
                                        setSystemPromptModalOpen(true)
                                    }}
                                >
                                    编辑系统提示词
                                </Button>
                                <Tooltip title="法则列表">
                                    <Button
                                        size="small"
                                        icon={<FileTextOutlined />}
                                        onClick={() => {
                                            if (deepseekConfig.lawRules.length > 0) {
                                                Modal.info({
                                                    title: '天机法则列表',
                                                    width: 600,
                                                    content: (
                                                        <div style={{ marginTop: 16 }}>
                                                            {deepseekConfig.lawRules.map((rule) => (
                                                                <div key={rule.id} style={{ marginBottom: 8, padding: '6px 8px', background: 'rgba(148,163,184,0.06)', borderRadius: 4 }}>
                                                                    <Text strong style={{ fontSize: 12 }}>{rule.name}</Text>
                                                                    <br />
                                                                    <Text type="secondary" style={{ fontSize: 11 }}>{rule.description}</Text>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    ),
                                                })
                                            } else {
                                                message.info('暂无法则数据')
                                            }
                                        }}
                                    >
                                        法则列表 ({deepseekConfig.lawRules.length})
                                    </Button>
                                </Tooltip>
                            </Space>
                        </Col>
                    </Row>
                    {deepseekConfig.useLawPrompt && (
                        <Alert
                            type="success"
                            showIcon
                            message="已注入天机法则+常识系统提示词"
                            description="每次对话将自动注入天机宪法、开发法则体系、常识类法则等系统提示词，确保AI遵循天机规范。"
                            style={{ marginTop: 8, fontSize: 12 }}
                        />
                    )}
                </div>
            </Card>
        </div>
    )

    const tabItems = [
        {
            key: 'memory',
            label: (
                <span>
                    <DatabaseOutlined />
                    记忆层
                </span>
            ),
            children: renderMemoryConfig(),
        },
        {
            key: 'mcp',
            label: (
                <span>
                    <ApiOutlined />
                    MCP服务器
                </span>
            ),
            children: renderMcpConfig(),
        },
        {
            key: 'agents',
            label: (
                <span>
                    <RobotOutlined />
                    Agents
                </span>
            ),
            children: renderAgentConfig(),
        },
        {
            key: 'skills',
            label: (
                <span>
                    <FileTextOutlined />
                    Skills
                </span>
            ),
            children: renderSkillConfig(),
        },
        {
            key: 'deepseek',
            label: (
                <span>
                    <BulbOutlined />
                    DeepSeek大脑
                </span>
            ),
            children: renderDeepSeekConfig(),
        },
    ]

    return (
        <div>
            <Card
                size="small"
                title={
                    <Space>
                        <SettingOutlined style={{ color: '#1890ff' }} />
                        <Text strong style={{ fontSize: 16 }}>
                            系统配置
                        </Text>
                        <Tag color="blue">v9.1 ONEDIR</Tag>
                    </Space>
                }
                extra={
                    <Space>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                            {error ? '离线模式' : '在线·已连接'}
                        </Text>
                        <Button
                            type="primary"
                            size="small"
                            icon={<SaveOutlined />}
                            onClick={handleSave}
                            loading={saving}
                        >
                            保存配置
                        </Button>
                        <Button size="small" icon={<ReloadOutlined />} onClick={fetchConfig}>
                            重新加载
                        </Button>
                    </Space>
                }
                styles={{ body: { padding: '12px' } }}
            >
                <Form form={form} layout="vertical" size="small" initialValues={config || DEFAULT_CONFIG}>
                    <Tabs items={tabItems} tabPosition="left" style={{ minHeight: 400 }} />
                </Form>
            </Card>

            <Card size="small" title="系统信息" style={{ marginTop: 16 }}>
                <Row gutter={[16, 16]}>
                    <Col xs={24} sm={12} lg={6}>
                        <Descriptions column={1} size="small" bordered>
                            <Descriptions.Item label="版本">天机 v9.1 ONEDIR</Descriptions.Item>
                            <Descriptions.Item label="打包方式">PyInstaller --onedir</Descriptions.Item>
                            <Descriptions.Item label="Python运行时">
                                <Text code>D:\元初系统\天机v9.1\deploy</Text>
                            </Descriptions.Item>
                        </Descriptions>
                    </Col>
                    <Col xs={24} sm={12} lg={6}>
                        <Descriptions column={1} size="small" bordered>
                            <Descriptions.Item label="Web端口">8771 (统一端口)</Descriptions.Item>
                            <Descriptions.Item label="MCP服务器">
                                {/* [FIX-FAB-005] 真实数据 */}
                                {systemStats ? systemStats.mcpCount : '-'}
                            </Descriptions.Item>
                            <Descriptions.Item label="API端点">
                                {systemStats ? (systemStats.apiEndpoints || '-') : '-'}
                            </Descriptions.Item>
                        </Descriptions>
                    </Col>
                    <Col xs={24} sm={12} lg={6}>
                        <Descriptions column={1} size="small" bordered>
                            <Descriptions.Item label="Agent总数">
                                {systemStats ? systemStats.agentCount : '-'}
                            </Descriptions.Item>
                            <Descriptions.Item label="L1守护 Agent">
                                {systemStats ? systemStats.agentL1 : '-'}
                            </Descriptions.Item>
                            <Descriptions.Item label="L2执行 Agent">
                                {systemStats ? systemStats.agentL2 : '-'}
                            </Descriptions.Item>
                            <Descriptions.Item label="L3决策 Agent">
                                {systemStats ? systemStats.agentL3 : '-'}
                            </Descriptions.Item>
                        </Descriptions>
                    </Col>
                    <Col xs={24} sm={12} lg={6}>
                        <Descriptions column={1} size="small" bordered>
                            <Descriptions.Item label="Skill总数">
                                {systemStats ? systemStats.skillCount : '-'}
                            </Descriptions.Item>
                            <Descriptions.Item label="记忆层">
                                {systemStats ? `${systemStats.memoryLayers}层 (ICME架构)` : '-'}
                            </Descriptions.Item>
                            <Descriptions.Item label="项目根目录">
                                <Text code>D:\元初系统</Text>
                            </Descriptions.Item>
                        </Descriptions>
                    </Col>
                </Row>
            </Card>

            {/* ✅ DeepSeek: API密钥修改Modal */}
            <Modal
                title={
                    <Space>
                        <KeyOutlined />
                        <span>修改 DeepSeek API 密钥</span>
                    </Space>
                }
                open={apiKeyModalOpen}
                onOk={handleSaveApiKey}
                onCancel={() => {
                    setApiKeyModalOpen(false)
                    setNewApiKey('')
                }}
                okText="保存"
                cancelText="取消"
                width={500}
                destroyOnClose
            >
                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                    <Alert
                        type="info"
                        showIcon
                        message="从 https://platform.deepseek.com 获取API密钥"
                        description="密钥格式: sk-xxxxxxxxxxxxxxxxxxxxxxxx。保存后立即生效。"
                        style={{ fontSize: 12 }}
                    />
                    <Input.Password
                        placeholder="sk-xxxxxxxxxxxxxxxxxxxxxxxx"
                        value={newApiKey}
                        onChange={(e) => setNewApiKey(e.target.value)}
                        visibilityToggle
                        autoFocus
                    />
                    {deepseekConfig.apiKeyMasked && (
                        <Text type="secondary" style={{ fontSize: 11 }}>
                            当前密钥: {deepseekConfig.apiKeyMasked}
                        </Text>
                    )}
                </Space>
            </Modal>

            {/* ✅ DeepSeek: 系统提示词查看Modal */}
            <Modal
                title={
                    <Space>
                        <EyeOutlined />
                        <span>查看系统提示词</span>
                    </Space>
                }
                open={systemPromptViewOpen}
                onCancel={() => setSystemPromptViewOpen(false)}
                footer={[
                    <Button key="close" onClick={() => setSystemPromptViewOpen(false)}>
                        关闭
                    </Button>,
                    <Button
                        key="edit"
                        type="primary"
                        icon={<EditOutlined />}
                        onClick={() => {
                            setEditingSystemPrompt(deepseekConfig.systemPrompt)
                            setSystemPromptViewOpen(false)
                            setSystemPromptModalOpen(true)
                        }}
                    >
                        编辑
                    </Button>,
                ]}
                width={700}
            >
                <pre
                    style={{
                        maxHeight: 400,
                        overflow: 'auto',
                        background: 'rgba(148,163,184,0.06)',
                        padding: 12,
                        borderRadius: 6,
                        fontSize: 12,
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                    }}
                >
                    {deepseekConfig.systemPrompt || '(系统提示词为空，将使用默认提示词)'}
                </pre>
            </Modal>

            {/* ✅ DeepSeek: 系统提示词编辑Modal */}
            <Modal
                title={
                    <Space>
                        <EditOutlined />
                        <span>编辑系统提示词</span>
                    </Space>
                }
                open={systemPromptModalOpen}
                onOk={handleSaveSystemPrompt}
                onCancel={() => {
                    setSystemPromptModalOpen(false)
                    setEditingSystemPrompt('')
                }}
                okText="保存"
                cancelText="取消"
                width={700}
                destroyOnClose
            >
                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                    <Alert
                        type="warning"
                        showIcon
                        message="系统提示词将影响所有对话的AI行为"
                        description="修改系统提示词后，新对话将使用新的提示词。已有对话不受影响。"
                        style={{ fontSize: 12 }}
                    />
                    <Input.TextArea
                        value={editingSystemPrompt}
                        onChange={(e) => setEditingSystemPrompt(e.target.value)}
                        autoSize={{ minRows: 8, maxRows: 20 }}
                        placeholder="输入系统提示词..."
                    />
                    <Text type="secondary" style={{ fontSize: 11 }}>
                        字符数: {editingSystemPrompt.length}
                    </Text>
                </Space>
            </Modal>
        </div>
    )
}
