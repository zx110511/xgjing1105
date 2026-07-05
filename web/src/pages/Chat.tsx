import { useState, useRef, useEffect, useCallback } from 'react'
import {
    Input,
    Button,
    Avatar,
    Space,
    Tooltip,
    message,
    Modal,
    Tag,
    Switch,
    Segmented,
    Popconfirm,
} from 'antd'
import type { SegmentedValue } from 'antd/es/segmented'
import {
    SendOutlined,
    ClearOutlined,
    RobotOutlined,
    UserOutlined,
    CopyOutlined,
    CheckOutlined,
    LoadingOutlined,
    PlusOutlined,
    MenuFoldOutlined,
    MenuUnfoldOutlined,
    DeleteOutlined,
    EditOutlined,
    StopOutlined,
    FileTextOutlined,
    DatabaseOutlined,
    SearchOutlined,
    DownloadOutlined,
    PushpinOutlined,
    PushpinFilled,
    UploadOutlined,
    BarChartOutlined,
    ThunderboltOutlined,
    TeamOutlined,
    SwapOutlined,
    BulbOutlined,
    ReloadOutlined,
} from '@ant-design/icons'
import OperationTransparencyInline, {
    OpTransparencyEvent,
} from '../components/OperationTransparencyInline'
import MemoryOpsPanel from '../components/MemoryOpsPanel'
import ReactMarkdown from 'react-markdown'
import { api } from '../services/api'
import { chatStorage } from '../services/chat-storage'

const { TextArea } = Input

interface Message {
    id: string
    role: 'user' | 'assistant' | 'system'
    content: string
    timestamp: number
    opEvents?: OpTransparencyEvent[]
    isStreaming?: boolean
    tokenCount?: number
    fidelity?: string
    reasoningContent?: string
    isEdited?: boolean
    modelMode?: string
    thinkingEnabled?: boolean
}

type ModelMode = 'v4-flash' | 'v4-pro'
type ReasoningEffort = 'low' | 'medium' | 'high'

interface DeepSeekSettings {
    modelMode: ModelMode
    thinkingEnabled: boolean
    reasoningEffort: ReasoningEffort
    useLawPrompt: boolean
}

const DEFAULT_DEEPSEEK_SETTINGS: DeepSeekSettings = {
    modelMode: 'v4-flash',
    thinkingEnabled: false,
    reasoningEffort: 'medium',
    useLawPrompt: true,
}

const DEEPSEEK_SETTINGS_KEY = 'tianji_deepseek_settings'

function loadDeepSeekSettings(): DeepSeekSettings {
    try {
        const stored = localStorage.getItem(DEEPSEEK_SETTINGS_KEY)
        if (stored) {
            const parsed = JSON.parse(stored) as Partial<DeepSeekSettings>
            return { ...DEFAULT_DEEPSEEK_SETTINGS, ...parsed }
        }
    } catch {
        // ignore parse errors
    }
    return DEFAULT_DEEPSEEK_SETTINGS
}

function saveDeepSeekSettings(settings: DeepSeekSettings): void {
    try {
        localStorage.setItem(DEEPSEEK_SETTINGS_KEY, JSON.stringify(settings))
    } catch {
        // ignore quota errors
    }
}

// [FIX-chat-xml-002] 字符净化器: 修复外部拦截层造成的字符替换
const GARBLED_CHAR_MAP: Record<string, string> = {
    '《': '<',
    '》': '>',
    '纳么': 'name=',
    '时态日你哥': 'blocking=',
    '安然么特人': 'parameter',
    '女哦可': 'invoke',
    '让么特人': 'parameter',
    '阿么timeout': 'timeout',
    '纳me': 'name',
    'ool_calls': 'tool_calls',
    '阿me': 'name',
}

function sanitizeGarbledText(text: string): string {
    let cleaned = text
    for (const [garbled, correct] of Object.entries(GARBLED_CHAR_MAP)) {
        cleaned = cleaned.split(garbled).join(correct)
    }
    return cleaned
}

// [FIX-chat-xml-003] XML标签过滤: 移除所有工具调用XML标记
function stripToolCallXml(text: string): string {
    return text
        .replace(/<tool_calls>[\s\S]*?<\/tool_calls>/gi, '')
        .replace(/<invoke[\s\S]*?<\/invoke>/gi, '')
        .replace(/<parameter[\s\S]*?<\/parameter>/gi, '')
        .replace(/<function_call[\s\S]*?<\/function_call>/gi, '')
        .replace(/<\/?(tool_calls|invoke|parameter|function_call)[^>]*>/gi, '')
        .replace(/<｜｜DSML｜｜>/g, '')
        .replace(/｜｜/g, '')
}

// [FIX-chat-xml-004] 低质量回复检测: 识别AI重复用户输入等弱智行为
function detectLowQualityResponse(userInput: string, aiResponse: string): boolean {
    if (!userInput || !aiResponse) return false
    // 检测1: AI回复包含完整用户输入(重复)
    if (aiResponse.includes(userInput) && userInput.length > 5) return true
    // 检测2: AI回复包含时间戳模式(无意义拼接)
    if (/\d{2}:\d{2}:\d{2}/.test(aiResponse) && aiResponse.length < 50) return true
    // 检测3: AI回复过短且无实质内容
    if (aiResponse.trim().length < 10) return true
    // 检测4: AI回复包含工具调用XML残留(未执行)
    if (/<tool_calls|<invoke|<parameter/i.test(aiResponse)) return true
    return false
}

interface ConversationItem {
    id: string
    title: string
    message_count: number
    total_tokens: number
    summary: string
    created_at: number
    updated_at: number
    pinned?: boolean
}

export default function Chat() {
    const [messages, setMessages] = useState<Message[]>([])
    const [input, setInput] = useState('')
    const [loading, setLoading] = useState(false)
    const [conversationId, setConversationId] = useState<string>(() => {
        const stored = sessionStorage.getItem('tianji_chat_conv_id')
        return stored || ''
    })
    const [conversations, setConversations] = useState<ConversationItem[]>([])
    const [sidebarOpen, setSidebarOpen] = useState(true)
    const [copiedId, setCopiedId] = useState<string | null>(null)
    const [editingTitle, setEditingTitle] = useState<string | null>(null)
    const [tokenCount, setTokenCount] = useState(0)
    const messagesEndRef = useRef<HTMLDivElement>(null)
    const abortRef = useRef<AbortController | null>(null)
    const [memoryPanelOpen, setMemoryPanelOpen] = useState(false)
    const [offlineMode, setOfflineMode] = useState(false)
    const [searchQuery, setSearchQuery] = useState('')
    const [searchResults, setSearchResults] = useState<ConversationItem[]>([])
    // [FIX-TS-013] 删除未使用的 isSearching state (setter 调用保留以备将来使用)
    const [showStats, setShowStats] = useState(false)

    // ✅ v9.1融合系统状态
    const [currentAgent, setCurrentAgent] = useState<{ id: string; name: string; emoji: string; layer: string; role: string }>({
        id: 'tianshu', name: '天枢', emoji: '🎯', layer: 'L2', role: '总指挥',
    })
    const [skillSuggestions, setSkillSuggestions] = useState<string[]>([])
    const [toolCallResults, setToolCallResults] = useState<{ toolName: string; result: string; timestamp: number }[]>([])
    const [fusionHealth, setFusionHealth] = useState<{ mcp_bridge: boolean; skill_resolver: boolean; agent_broker: boolean }>({
        mcp_bridge: false, skill_resolver: false, agent_broker: false,
    })
    // ✅ v9.1 UX优化: 对话体验增强状态
    // [FIX-TS-013] 删除未使用的 retryCount/lastFailedInput/contextMemory state
    const [showWelcome] = useState(() => !sessionStorage.getItem('tianji_welcomed'))

    // ✅ DeepSeek V4-Pro/V4-Flash 双模式 + Thinking + 法则提示词
    const [deepseekSettings, setDeepseekSettings] = useState<DeepSeekSettings>(() => loadDeepSeekSettings())
    const [editingMessage, setEditingMessage] = useState<Message | null>(null)
    const [editContent, setEditContent] = useState('')
    const [regeneratingId, setRegeneratingId] = useState<string | null>(null)
    const [expandedReasoning, setExpandedReasoning] = useState<Set<string>>(new Set())

    useEffect(() => {
        saveDeepSeekSettings(deepseekSettings)
    }, [deepseekSettings])

    const toggleReasoningExpand = useCallback((msgId: string) => {
        setExpandedReasoning((prev) => {
            const next = new Set(prev)
            if (next.has(msgId)) {
                next.delete(msgId)
            } else {
                next.add(msgId)
            }
            return next
        })
    }, [])

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }

    useEffect(() => {
        scrollToBottom()
    }, [messages])

    const fetchConversations = useCallback(async () => {
        try {
            const res = await api.get<{ success: boolean; conversations: ConversationItem[] }>(
                '/api/chat/conversations?limit=50'
            )
            if (res.success) {
                setConversations(res.conversations || [])
            }
        } catch {
            // silent
        }
    }, [])

    useEffect(() => {
        fetchConversations()
    }, [fetchConversations])

    // ✅ v9.1融合: 加载融合系统健康状态
    useEffect(() => {
        const checkFusionHealth = async () => {
            try {
                const res = await api.get<{ success: boolean; fusion_systems: Record<string, { status: string }> }>(
                    '/api/chat/fusion/health'
                )
                if (res.success && res.fusion_systems) {
                    setFusionHealth({
                        mcp_bridge: res.fusion_systems.mcp_bridge?.status === 'healthy',
                        skill_resolver: res.fusion_systems.skill_resolver?.status === 'healthy',
                        agent_broker: res.fusion_systems.agent_broker?.status === 'healthy',
                    })
                }
            } catch {
                // 融合系统可能未就绪
            }
        }
        checkFusionHealth()
        const interval = setInterval(checkFusionHealth, 30000)
        return () => clearInterval(interval)
    }, [])

    // P3: IndexedDB 本地持久化 — 保存消息到本地
    useEffect(() => {
        if (messages.length > 0) {
            const currentTitle = conversations.find((c) => c.id === conversationId)?.title
            const convToStore = {
                id: conversationId || 'local_draft',
                title: currentTitle || '本地草稿',
                messages: messages.map((m) => ({
                    id: m.id,
                    role: m.role,
                    content: m.content,
                    timestamp: m.timestamp,
                    tokenCount: m.tokenCount,
                    fidelity: m.fidelity,
                })),
                messageCount: messages.length,
                totalTokens: tokenCount,
                createdAt: messages[0]?.timestamp || Date.now(),
                updatedAt: Date.now(),
                synced: !!conversationId && !offlineMode,
            }
            chatStorage.saveConversation(convToStore).catch(() => { })
        }
    }, [messages, conversationId, tokenCount, offlineMode, conversations])

    // P3: 服务端不可用时，从IndexedDB恢复本地对话
    const tryRestoreLocal = useCallback(async () => {
        try {
            const localConvs = await chatStorage.loadAllConversations()
            if (localConvs.length > 0 && !conversationId) {
                // 如果有本地未同步的对话，提示用户
                const unsynced = localConvs.filter((c) => !c.synced)
                if (unsynced.length > 0) {
                    setOfflineMode(true)
                }
            }
        } catch {
            /* ignore */
        }
    }, [conversationId])

    useEffect(() => {
        tryRestoreLocal()
    }, [tryRestoreLocal])

    const loadConversation = useCallback(async (convId: string) => {
        try {
            const res = await api.get<{
                success: boolean
                conversation: { messages?: Array<Record<string, unknown>>; total_tokens?: number }
            }>(`/api/chat/conversations/${convId}?include_messages=true`)
            if (res.success && res.conversation) {
                const conv = res.conversation
                setMessages(
                    (conv.messages || []).map((m: Record<string, unknown>) => ({
                        id: m.id as string,
                        role: ((m.role as string) || 'user') as Message['role'],
                        content: (m.content as string) || '',
                        timestamp: (m.timestamp as number) || Date.now(),
                        tokenCount: (m.token_count as number) || 0,
                        fidelity: (m.fidelity as string) || 'full',
                        isStreaming: false,
                    }))
                )
                setTokenCount(conv.total_tokens || 0)
                setConversationId(convId)
                sessionStorage.setItem('tianji_chat_conv_id', convId)
                setOfflineMode(false)
                chatStorage.markSynced(convId).catch(() => { })
            }
        } catch {
            // P3: 服务端不可用时尝试IndexedDB恢复
            const localConv = await chatStorage.loadConversation(convId)
            if (localConv?.messages) {
                setMessages(localConv.messages.map((m) => ({ ...m, opEvents: [], isStreaming: false })))
                setTokenCount(localConv.totalTokens || 0)
                setConversationId(convId)
                setOfflineMode(true)
                message.info('已从本地缓存加载对话（离线模式）')
            } else {
                message.error('加载对话失败')
            }
        }
    }, [])

    const createNewConversation = useCallback(() => {
        setMessages([])
        setConversationId('')
        setTokenCount(0)
        sessionStorage.removeItem('tianji_chat_conv_id')
    }, [])

    const deleteConversation = useCallback(
        async (convId: string) => {
            try {
                await api.delete(`/api/chat/conversations/${convId}`)
                if (conversationId === convId) createNewConversation()
                fetchConversations()
            } catch {
                message.error('删除失败')
            }
        },
        [conversationId, createNewConversation, fetchConversations]
    )

    const updateConversationTitle = useCallback(
        async (convId: string, title: string) => {
            try {
                await api.patch(
                    `/api/chat/conversations/${convId}/title?title=${encodeURIComponent(title)}`
                )
                setEditingTitle(null)
                fetchConversations()
            } catch {
                message.error('重命名失败')
            }
        },
        [fetchConversations]
    )

    const togglePin = useCallback(
        async (convId: string, currentPinned: boolean) => {
            try {
                await api.patch(`/api/chat/conversations/${convId}/pin?pinned=${!currentPinned}`)
                fetchConversations()
            } catch {
                message.error('置顶操作失败')
            }
        },
        [fetchConversations]
    )

    const handleSearch = useCallback(async () => {
        if (!searchQuery.trim()) {
            setSearchResults([])
            return
        }
        try {
            const res = await api.get<{
                success: boolean
                results: ConversationItem[]
            }>(`/api/chat/conversations/search?q=${encodeURIComponent(searchQuery)}&limit=20`)
            if (res.success) {
                setSearchResults(res.results || [])
            }
        } catch {
            message.error('搜索失败')
        }
    }, [searchQuery])

    const exportConversation = useCallback(async (convId: string, format: string = 'markdown') => {
        try {
            const baseUrl = window.location.origin
            const url = `${baseUrl}/api/chat/conversations/${convId}/export?format=${format}`
            const a = document.createElement('a')
            a.href = url
            a.download = ''
            document.body.appendChild(a)
            a.click()
            document.body.removeChild(a)
            message.success('导出成功')
        } catch {
            message.error('导出失败')
        }
    }, [])

    const exportAllConversations = useCallback(async () => {
        try {
            const baseUrl = window.location.origin
            const url = `${baseUrl}/api/chat/conversations/export-all`
            const a = document.createElement('a')
            a.href = url
            a.download = ''
            document.body.appendChild(a)
            a.click()
            document.body.removeChild(a)
            message.success('全部导出成功')
        } catch {
            message.error('导出失败')
        }
    }, [])

    const importConversations = useCallback(() => {
        const input = document.createElement('input')
        input.type = 'file'
        input.accept = '.json'
        input.onchange = async (e) => {
            const file = (e.target as HTMLInputElement).files?.[0]
            if (!file) return
            try {
                const text = await file.text()
                const data = JSON.parse(text)
                const res = await api.post<{ success: boolean; imported: number; skipped: number }>(
                    '/api/chat/conversations/import',
                    data
                )
                if (res.success) {
                    message.success(`导入完成: ${res.imported} 个对话, 跳过 ${res.skipped} 个`)
                    fetchConversations()
                }
            } catch {
                message.error('导入失败，请检查文件格式')
            }
        }
        input.click()
    }, [fetchConversations])

    // [FIX-TS-013] 删除未使用的 generateSummary 函数 (原已有 eslint-disable, 但 tsc 仍报错)
    // 如需恢复摘要功能, 可重新添加并实际调用此函数

    const handleAbort = useCallback(async () => {
        if (abortRef.current) {
            abortRef.current.abort()
            abortRef.current = null
        }
        if (conversationId) {
            try {
                await api.post(`/api/chat/abort?conversation_id=${conversationId}`)
            } catch {
                /* silent */
            }
        }
        setLoading(false)
        setMessages((prev) => prev.map((m) => (m.isStreaming ? { ...m, isStreaming: false } : m)))
    }, [conversationId])

    const handleSend = useCallback(async () => {
        if (!input.trim() || loading) return
        const userMessage = input.trim()
        setInput('')
        setLoading(true)

        const userMsg: Message = {
            id: `user-${Date.now()}`,
            role: 'user',
            content: userMessage,
            timestamp: Date.now(),
        }
        setMessages((prev) => [...prev, userMsg])

        const assistantId = `assistant-${Date.now()}`
        const assistantMsg: Message = {
            id: assistantId,
            role: 'assistant',
            content: '',
            timestamp: Date.now(),
            opEvents: [],
            isStreaming: true,
        }
        setMessages((prev) => [...prev, assistantMsg])

        const abortController = new AbortController()
        abortRef.current = abortController

        try {
            const baseUrl = window.location.origin
            const response = await fetch(`${baseUrl}/api/chat/stream`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: userMessage,
                    conversation_id: conversationId || undefined,
                    enable_memory: true,
                    enable_tools: true,
                    enable_transparency: true,
                    model_mode: deepseekSettings.modelMode,
                    thinking_enabled: deepseekSettings.modelMode === 'v4-pro' ? deepseekSettings.thinkingEnabled : false,
                    reasoning_effort: deepseekSettings.modelMode === 'v4-pro' && deepseekSettings.thinkingEnabled
                        ? deepseekSettings.reasoningEffort
                        : undefined,
                    use_law_prompt: deepseekSettings.useLawPrompt,
                }),
                signal: abortController.signal,
            })

            if (!response.ok) throw new Error(`HTTP ${response.status}`)

            const newConvId = response.headers.get('X-Conversation-Id')
            if (newConvId && !conversationId) {
                setConversationId(newConvId)
                sessionStorage.setItem('tianji_chat_conv_id', newConvId)
            }

            const reader = response.body?.getReader()
            if (!reader) throw new Error('No reader')

            const decoder = new TextDecoder()
            let buffer = ''
            let fullContent = ''

            while (true) {
                const { done, value } = await reader.read()
                if (done) break

                buffer += decoder.decode(value, { stream: true })
                const chunks = buffer.split('\n\n')
                buffer = chunks.pop() || ''

                for (const chunk of chunks) {
                    const lines = chunk.split('\n')
                    let eventType = ''
                    let dataLine = ''

                    for (const line of lines) {
                        if (line.startsWith('event: ')) {
                            eventType = line.slice(7).trim()
                        } else if (line.startsWith('data: ')) {
                            dataLine = line.slice(6).trim()
                        }
                    }

                    if (!dataLine) continue
                    // currentEventType tracks SSE event type for debugging

                    try {
                        const data = JSON.parse(dataLine)

                        switch (eventType) {
                            case 'meta':
                                if (data.conversation_id) {
                                    setConversationId(data.conversation_id)
                                    sessionStorage.setItem('tianji_chat_conv_id', data.conversation_id)
                                }
                                if (data.total_tokens !== undefined) setTokenCount(data.total_tokens)
                                // ✅ DeepSeek: 记录模型模式和thinking信息到assistant消息
                                if (data.model_mode || data.thinking_enabled !== undefined) {
                                    setMessages((prev) =>
                                        prev.map((m) =>
                                            m.id === assistantId
                                                ? {
                                                    ...m,
                                                    modelMode: data.model_mode || deepseekSettings.modelMode,
                                                    thinkingEnabled: data.thinking_enabled ?? false,
                                                }
                                                : m
                                        )
                                    )
                                }
                                break

                            case 'text_delta':
                                if (data.text) {
                                    // [FIX-chat-xml-002/003] 字符净化 + XML标签过滤
                                    const cleanedText = stripToolCallXml(sanitizeGarbledText(data.text))
                                    if (cleanedText.trim()) {
                                        fullContent += cleanedText
                                        setMessages((prev) =>
                                            prev.map((m) => (m.id === assistantId ? { ...m, content: fullContent } : m))
                                        )
                                    }
                                }
                                // ✅ DeepSeek: 处理推理内容 (reasoning_content)
                                if (data.reasoning_content) {
                                    setMessages((prev) =>
                                        prev.map((m) =>
                                            m.id === assistantId
                                                ? {
                                                    ...m,
                                                    reasoningContent: (m.reasoningContent || '') + data.reasoning_content,
                                                }
                                                : m
                                        )
                                    )
                                }
                                if (data.token_count) {
                                    setMessages((prev) =>
                                        prev.map((m) =>
                                            m.id === assistantId ? { ...m, tokenCount: data.token_count } : m
                                        )
                                    )
                                }
                                break

                            case 'reasoning_delta':
                                // ✅ DeepSeek: 独立的推理内容事件
                                if (data.reasoning_content || data.text) {
                                    const reasoningChunk = data.reasoning_content || data.text || ''
                                    setMessages((prev) =>
                                        prev.map((m) =>
                                            m.id === assistantId
                                                ? {
                                                    ...m,
                                                    reasoningContent: (m.reasoningContent || '') + reasoningChunk,
                                                }
                                                : m
                                        )
                                    )
                                }
                                break

                            case 'guardrail_triggered':
                                setMessages((prev) =>
                                    prev.map((m) =>
                                        m.id === assistantId
                                            ? {
                                                ...m,
                                                content:
                                                    (m.content || '') + `\n\n🛡️ Guardrail: ${data.action} — ${data.reason}`,
                                            }
                                            : m
                                    )
                                )
                                break

                            case 'memory_recall':
                                setMessages((prev) =>
                                    prev.map((m) =>
                                        m.id === assistantId
                                            ? {
                                                ...m,
                                                opEvents: [
                                                    ...(m.opEvents || []),
                                                    {
                                                        type: 'memory',
                                                        action: data.status || 'recall',
                                                        detail: `Query: ${data.query || ''}`,
                                                        color: '#06B6D4',
                                                        label: 'Memory',
                                                        desc: 'Memory Ops',
                                                        timestamp: Date.now(),
                                                        time_str: data.time_str || '',
                                                        status: data.status || 'done',
                                                    } as OpTransparencyEvent,
                                                ],
                                            }
                                            : m
                                    )
                                )
                                break

                            // ✅ v9.1融合: Skill推荐事件
                            case 'skill_suggestions':
                                if (data.suggestions) {
                                    setSkillSuggestions(data.suggestions)
                                }
                                break

                            // ✅ v9.1融合: Agent切换事件
                            case 'handoff':
                                if (data.to_agent) {
                                    setCurrentAgent({
                                        id: data.to_agent || 'tianshu',
                                        name: data.to_agent || '天枢',
                                        emoji: data.emoji || '🎯',
                                        layer: data.layer || 'L2',
                                        role: data.role || '总指挥',
                                    })
                                }
                                setMessages((prev) =>
                                    prev.map((m) =>
                                        m.id === assistantId
                                            ? {
                                                ...m,
                                                opEvents: [
                                                    ...(m.opEvents || []),
                                                    {
                                                        type: 'agent',
                                                        action: 'handoff',
                                                        detail: data.tvp || `${data.from_agent} → ${data.to_agent}`,
                                                        color: '#F59E0B',
                                                        label: 'Agent',
                                                        desc: 'TVP Handoff',
                                                        timestamp: Date.now(),
                                                        time_str: new Date().toLocaleTimeString(),
                                                        status: 'done',
                                                    } as OpTransparencyEvent,
                                                ],
                                            }
                                            : m
                                    )
                                )
                                break

                            // ✅ v9.1融合: 工具调用结果事件
                            case 'tool_call_done':
                                if (data.tool_name && data.result) {
                                    setToolCallResults((prev) => [
                                        ...prev.slice(-9),
                                        { toolName: data.tool_name, result: data.result, timestamp: Date.now() },
                                    ])
                                    setMessages((prev) =>
                                        prev.map((m) =>
                                            m.id === assistantId
                                                ? {
                                                    ...m,
                                                    opEvents: [
                                                        ...(m.opEvents || []),
                                                        {
                                                            type: 'tool',
                                                            action: data.tool_name,
                                                            detail: typeof data.result === 'string' ? data.result.slice(0, 100) : JSON.stringify(data.result).slice(0, 100),
                                                            color: '#10B981',
                                                            label: 'Tool',
                                                            desc: data.tool_name,
                                                            timestamp: Date.now(),
                                                            time_str: new Date().toLocaleTimeString(),
                                                            status: 'done',
                                                        } as OpTransparencyEvent,
                                                    ],
                                                }
                                                : m
                                        )
                                    )
                                }
                                break

                            // ✅ v9.1融合: 记忆存储事件
                            case 'memory_store':
                                setMessages((prev) =>
                                    prev.map((m) =>
                                        m.id === assistantId
                                            ? {
                                                ...m,
                                                opEvents: [
                                                    ...(m.opEvents || []),
                                                    {
                                                        type: 'memory',
                                                        action: data.status || 'store',
                                                        detail: `Layer: ${data.layer || '?'} | Source: ${data.source || '?'}`,
                                                        color: '#8B5CF6',
                                                        label: 'Memory',
                                                        desc: 'Memory Store',
                                                        timestamp: Date.now(),
                                                        time_str: data.time_str || '',
                                                        status: data.status || 'done',
                                                    } as OpTransparencyEvent,
                                                ],
                                            }
                                            : m
                                    )
                                )
                                break

                            case 'done':
                                setTokenCount(data.total_tokens || tokenCount)
                                // [FIX-chat-xml-004] 低质量回复检测
                                if (detectLowQualityResponse(userMessage, fullContent)) {
                                    setMessages((prev) =>
                                        prev.map((m) =>
                                            m.id === assistantId
                                                ? {
                                                    ...m,
                                                    isStreaming: false,
                                                    content: fullContent + '\n\n⚠️ 检测到低质量回复(可能重复输入或未执行工具)，建议重新生成',
                                                }
                                                : m
                                        )
                                    )
                                } else {
                                    setMessages((prev) =>
                                        prev.map((m) => (m.id === assistantId ? { ...m, isStreaming: false } : m))
                                    )
                                }
                                fetchConversations()
                                break

                            case 'error':
                                setMessages((prev) =>
                                    prev.map((m) =>
                                        m.id === assistantId
                                            ? {
                                                ...m,
                                                content: (m.content || '') + `\n\n⚠️ ${data.detail}`,
                                                isStreaming: false,
                                            }
                                            : m
                                    )
                                )
                                break

                            default:
                                break
                        }
                    } catch {
                        // skip non-JSON lines
                    }
                }
            }

            setMessages((prev) =>
                prev.map((m) => (m.id === assistantId ? { ...m, isStreaming: false } : m))
            )
        } catch (err: unknown) {
            if ((err as Error).name === 'AbortError') {
                setMessages((prev) =>
                    prev.map((m) =>
                        m.id === assistantId
                            ? { ...m, content: (m.content || '') + '\n\n⏹️ *生成已停止*', isStreaming: false }
                            : m
                    )
                )
            } else {
                message.error('连接失败')
                setMessages((prev) =>
                    prev.map((m) =>
                        m.id === assistantId
                            ? { ...m, content: `❌ ${(err as Error).message}`, isStreaming: false }
                            : m
                    )
                )
            }
        } finally {
            setLoading(false)
            abortRef.current = null
        }
    }, [input, loading, conversationId, tokenCount, fetchConversations, deepseekSettings])

    useEffect(() => {
        const handleKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape' && loading) {
                handleAbort()
            }
        }
        window.addEventListener('keydown', handleKey)
        return () => window.removeEventListener('keydown', handleKey)
    }, [loading, handleAbort])

    const handleCopy = async (text: string, id: string) => {
        try {
            await navigator.clipboard.writeText(text)
            setCopiedId(id)
            setTimeout(() => setCopiedId(null), 2000)
        } catch {
            /* fallback */
        }
    }

    // ✅ DeepSeek: 消息编辑功能
    const handleEditMessage = useCallback(
        async (msg: Message) => {
            if (!editContent.trim() || !conversationId) {
                setEditingMessage(null)
                return
            }
            try {
                const res = await api.put<{ success: boolean }>(
                    `/api/chat/conversations/${conversationId}/messages/${msg.id}`,
                    { content: editContent.trim() }
                )
                if (res?.success !== false) {
                    setMessages((prev) =>
                        prev.map((m) =>
                            m.id === msg.id
                                ? { ...m, content: editContent.trim(), isEdited: true }
                                : m
                        )
                    )
                    message.success('消息已更新')
                }
            } catch {
                // 降级: 仅更新本地状态
                setMessages((prev) =>
                    prev.map((m) =>
                        m.id === msg.id
                            ? { ...m, content: editContent.trim(), isEdited: true }
                            : m
                    )
                )
                message.warning('服务端更新失败，已更新本地')
            } finally {
                setEditingMessage(null)
                setEditContent('')
            }
        },
        [editContent, conversationId]
    )

    // ✅ DeepSeek: 消息删除功能
    const handleDeleteMessage = useCallback(
        async (msgId: string) => {
            if (!conversationId) {
                setMessages((prev) => prev.filter((m) => m.id !== msgId))
                return
            }
            try {
                await api.delete(`/api/chat/conversations/${conversationId}/messages/${msgId}`)
                setMessages((prev) => prev.filter((m) => m.id !== msgId))
                message.success('消息已删除')
            } catch {
                // 降级: 仅更新本地状态
                setMessages((prev) => prev.filter((m) => m.id !== msgId))
                message.warning('服务端删除失败，已删除本地')
            }
        },
        [conversationId]
    )

    // ✅ DeepSeek: 重新生成AI回复
    const handleRegenerateMessage = useCallback(
        async (msg: Message) => {
            if (!conversationId || regeneratingId) return
            setRegeneratingId(msg.id)
            try {
                const baseUrl = window.location.origin
                const response = await fetch(
                    `${baseUrl}/api/chat/conversations/${conversationId}/messages/${msg.id}/regenerate`,
                    {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            model_mode: deepseekSettings.modelMode,
                            thinking_enabled: deepseekSettings.modelMode === 'v4-pro' ? deepseekSettings.thinkingEnabled : false,
                            reasoning_effort: deepseekSettings.modelMode === 'v4-pro' && deepseekSettings.thinkingEnabled
                                ? deepseekSettings.reasoningEffort
                                : undefined,
                            use_law_prompt: deepseekSettings.useLawPrompt,
                        }),
                    }
                )

                if (!response.ok) throw new Error(`HTTP ${response.status}`)

                const reader = response.body?.getReader()
                if (!reader) throw new Error('No reader')

                const decoder = new TextDecoder()
                let buffer = ''
                let fullContent = ''
                let fullReasoning = ''

                // 重置消息内容
                setMessages((prev) =>
                    prev.map((m) =>
                        m.id === msg.id
                            ? { ...m, content: '', reasoningContent: '', isStreaming: true }
                            : m
                    )
                )

                while (true) {
                    const { done, value } = await reader.read()
                    if (done) break

                    buffer += decoder.decode(value, { stream: true })
                    const chunks = buffer.split('\n\n')
                    buffer = chunks.pop() || ''

                    for (const chunk of chunks) {
                        const lines = chunk.split('\n')
                        let eventType = ''
                        let dataLine = ''

                        for (const line of lines) {
                            if (line.startsWith('event: ')) {
                                eventType = line.slice(7).trim()
                            } else if (line.startsWith('data: ')) {
                                dataLine = line.slice(6).trim()
                            }
                        }

                        if (!dataLine) continue

                        try {
                            const data = JSON.parse(dataLine)
                            switch (eventType) {
                                case 'text_delta':
                                    if (data.text) {
                                        // [FIX-chat-xml-002/003] 字符净化 + XML标签过滤 (regenerate路径)
                                        const regenCleaned = stripToolCallXml(sanitizeGarbledText(data.text))
                                        if (regenCleaned.trim()) {
                                            fullContent += regenCleaned
                                            setMessages((prev) =>
                                                prev.map((m) => (m.id === msg.id ? { ...m, content: fullContent } : m))
                                            )
                                        }
                                    }
                                    if (data.reasoning_content) {
                                        fullReasoning += data.reasoning_content
                                        setMessages((prev) =>
                                            prev.map((m) =>
                                                m.id === msg.id ? { ...m, reasoningContent: fullReasoning } : m
                                            )
                                        )
                                    }
                                    break
                                case 'reasoning_delta':
                                    if (data.reasoning_content || data.text) {
                                        fullReasoning += data.reasoning_content || data.text || ''
                                        setMessages((prev) =>
                                            prev.map((m) =>
                                                m.id === msg.id ? { ...m, reasoningContent: fullReasoning } : m
                                            )
                                        )
                                    }
                                    break
                                case 'done':
                                    setMessages((prev) =>
                                        prev.map((m) => (m.id === msg.id ? { ...m, isStreaming: false } : m))
                                    )
                                    break
                                case 'error':
                                    setMessages((prev) =>
                                        prev.map((m) =>
                                            m.id === msg.id
                                                ? {
                                                    ...m,
                                                    content: (m.content || '') + `\n\n⚠️ ${data.detail}`,
                                                    isStreaming: false,
                                                }
                                                : m
                                        )
                                    )
                                    break
                                default:
                                    break
                            }
                        } catch {
                            // skip non-JSON lines
                        }
                    }
                }

                setMessages((prev) =>
                    prev.map((m) => (m.id === msg.id ? { ...m, isStreaming: false } : m))
                )
                message.success('已重新生成回复')
            } catch (err: unknown) {
                message.error('重新生成失败')
                setMessages((prev) =>
                    prev.map((m) =>
                        m.id === msg.id
                            ? { ...m, content: `❌ ${(err as Error).message}`, isStreaming: false }
                            : m
                    )
                )
            } finally {
                setRegeneratingId(null)
            }
        },
        [conversationId, regeneratingId, deepseekSettings]
    )

    const openEditModal = useCallback((msg: Message) => {
        setEditingMessage(msg)
        setEditContent(msg.content)
    }, [])

    const cancelEdit = useCallback(() => {
        setEditingMessage(null)
        setEditContent('')
    }, [])

    const handleClear = () => {
        setMessages([])
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSend()
        }
    }

    const formatTime = (ts: number) => {
        const d = new Date(ts * 1000)
        const now = new Date()
        const diff = now.getTime() - d.getTime()
        if (diff < 60000) return '刚刚'
        if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
        return d.toLocaleDateString('zh-CN')
    }

    const activeConversation = conversations.find((c) => c.id === conversationId)

    return (
        <div
            style={{
                height: 'calc(100vh - 112px)',
                minHeight: 500,
                display: 'flex',
                background: '#0F172A',
                color: '#E2E8F0',
                fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Microsoft YaHei', sans-serif",
            }}
        >
            {/* Sidebar */}
            <div
                style={{
                    width: sidebarOpen ? 280 : 0,
                    overflow: 'hidden',
                    transition: 'width 0.2s',
                    borderRight: sidebarOpen ? '1px solid rgba(148,163,184,0.1)' : 'none',
                    display: 'flex',
                    flexDirection: 'column',
                    background: 'rgba(15,23,42,0.95)',
                    flexShrink: 0,
                }}
            >
                {sidebarOpen && (
                    <>
                        <div
                            style={{
                                padding: '12px 16px',
                                borderBottom: '1px solid rgba(148,163,184,0.08)',
                            }}
                        >
                            <Button
                                type="primary"
                                icon={<PlusOutlined />}
                                onClick={createNewConversation}
                                block
                                style={{
                                    background: 'linear-gradient(135deg, #8B5CF6, #7C3AED)',
                                    border: 'none',
                                    height: 36,
                                    marginBottom: 8,
                                }}
                            >
                                新对话
                            </Button>
                            {/* 搜索栏 */}
                            <Input
                                size="small"
                                placeholder="搜索对话..."
                                prefix={<SearchOutlined style={{ color: '#64748B' }} />}
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                onPressEnter={handleSearch}
                                allowClear
                                onClear={() => { setSearchQuery(''); setSearchResults([]) }}
                                style={{
                                    background: 'rgba(30,41,59,0.6)',
                                    border: '1px solid rgba(148,163,184,0.15)',
                                    color: '#E2E8F0',
                                    borderRadius: 6,
                                    marginBottom: 6,
                                }}
                            />
                            {/* 快捷操作栏 */}
                            <div style={{ display: 'flex', gap: 4 }}>
                                <Tooltip title="导出全部">
                                    <Button
                                        type="text"
                                        size="small"
                                        icon={<DownloadOutlined style={{ fontSize: 12 }} />}
                                        onClick={exportAllConversations}
                                        style={{ color: '#64748B', flex: 1, fontSize: 10 }}
                                    >
                                        导出
                                    </Button>
                                </Tooltip>
                                <Tooltip title="导入备份">
                                    <Button
                                        type="text"
                                        size="small"
                                        icon={<UploadOutlined style={{ fontSize: 12 }} />}
                                        onClick={importConversations}
                                        style={{ color: '#64748B', flex: 1, fontSize: 10 }}
                                    >
                                        导入
                                    </Button>
                                </Tooltip>
                                <Tooltip title="统计">
                                    <Button
                                        type="text"
                                        size="small"
                                        icon={<BarChartOutlined style={{ fontSize: 12 }} />}
                                        onClick={() => setShowStats(!showStats)}
                                        style={{ color: '#64748B', flex: 1, fontSize: 10 }}
                                    >
                                        统计
                                    </Button>
                                </Tooltip>
                            </div>
                        </div>
                        <div style={{ flex: 1, overflowY: 'auto', padding: '4px 8px' }}>
                            {/* 统计面板 */}
                            {showStats && (
                                <div style={{
                                    background: 'rgba(139,92,246,0.08)',
                                    border: '1px solid rgba(139,92,246,0.2)',
                                    borderRadius: 8,
                                    padding: '8px 12px',
                                    marginBottom: 8,
                                    fontSize: 11,
                                    color: '#94A3B8',
                                }}>
                                    <div>对话总数: {conversations.length}</div>
                                    <div>消息总数: {conversations.reduce((s, c) => s + c.message_count, 0)}</div>
                                    <div>置顶对话: {conversations.filter(c => c.pinned).length}</div>
                                    <div>Token总量: {conversations.reduce((s, c) => s + c.total_tokens, 0).toLocaleString()}</div>
                                </div>
                            )}
                            {/* 搜索结果 */}
                            {searchResults.length > 0 && (
                                <div style={{ marginBottom: 8 }}>
                                    <div style={{ fontSize: 10, color: '#8B5CF6', marginBottom: 4, padding: '0 4px' }}>
                                        搜索结果 ({searchResults.length})
                                    </div>
                                    {searchResults.map((conv) => (
                                        <div
                                            key={conv.id}
                                            onClick={() => { loadConversation(conv.id); setSearchResults([]); setSearchQuery('') }}
                                            style={{
                                                padding: '6px 10px',
                                                borderRadius: 6,
                                                cursor: 'pointer',
                                                marginBottom: 2,
                                                background: 'rgba(139,92,246,0.08)',
                                                border: '1px solid rgba(139,92,246,0.15)',
                                                fontSize: 12,
                                                color: '#E2E8F0',
                                            }}
                                        >
                                            {conv.title}
                                            <span style={{ fontSize: 10, color: '#64748B', marginLeft: 6 }}>
                                                {conv.message_count}条
                                            </span>
                                        </div>
                                    ))}
                                    <Button
                                        type="text"
                                        size="small"
                                        onClick={() => { setSearchResults([]); setSearchQuery('') }}
                                        style={{ color: '#64748B', fontSize: 10, width: '100%', marginTop: 2 }}
                                    >
                                        清除搜索
                                    </Button>
                                </div>
                            )}
                            {conversations.length === 0 && searchResults.length === 0 ? (
                                <div style={{ padding: 24, textAlign: 'center', color: '#475569', fontSize: 13 }}>
                                    暂无对话
                                </div>
                            ) : (
                                conversations.map((conv) => (
                                    <div
                                        key={conv.id}
                                        onClick={() => loadConversation(conv.id)}
                                        style={{
                                            padding: '8px 12px',
                                            borderRadius: 8,
                                            cursor: 'pointer',
                                            marginBottom: 2,
                                            background:
                                                conv.id === conversationId ? 'rgba(139,92,246,0.12)' : (conv.pinned ? 'rgba(250,173,20,0.06)' : 'transparent'),
                                            border:
                                                conv.id === conversationId
                                                    ? '1px solid rgba(139,92,246,0.3)'
                                                    : conv.pinned
                                                        ? '1px solid rgba(250,173,20,0.15)'
                                                        : '1px solid transparent',
                                            transition: 'all 0.15s',
                                        }}
                                        onMouseEnter={(e) => {
                                            if (conv.id !== conversationId)
                                                (e.currentTarget as HTMLDivElement).style.background = 'rgba(30,41,59,0.8)'
                                        }}
                                        onMouseLeave={(e) => {
                                            if (conv.id !== conversationId)
                                                (e.currentTarget as HTMLDivElement).style.background = conv.pinned ? 'rgba(250,173,20,0.06)' : 'transparent'
                                        }}
                                    >
                                        <div
                                            style={{
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'space-between',
                                            }}
                                        >
                                            <div style={{ flex: 1, minWidth: 0 }}>
                                                {editingTitle === conv.id ? (
                                                    <Input
                                                        size="small"
                                                        defaultValue={conv.title}
                                                        onPressEnter={(e) => {
                                                            const target = e.target as HTMLInputElement
                                                            updateConversationTitle(conv.id, target.value || conv.title)
                                                        }}
                                                        onBlur={(e) => {
                                                            updateConversationTitle(conv.id, e.target.value || conv.title)
                                                        }}
                                                        autoFocus
                                                        style={{
                                                            background: 'rgba(30,41,59,0.8)',
                                                            border: '1px solid rgba(139,92,246,0.3)',
                                                            color: '#E2E8F0',
                                                        }}
                                                        onClick={(e) => e.stopPropagation()}
                                                    />
                                                ) : (
                                                    <div
                                                        style={{
                                                            fontSize: 13,
                                                            fontWeight: conv.id === conversationId ? 600 : 400,
                                                            color: conv.id === conversationId ? '#E2E8F0' : '#94A3B8',
                                                            overflow: 'hidden',
                                                            textOverflow: 'ellipsis',
                                                            whiteSpace: 'nowrap',
                                                            display: 'flex',
                                                            alignItems: 'center',
                                                            gap: 4,
                                                        }}
                                                    >
                                                        {conv.pinned && <PushpinFilled style={{ fontSize: 10, color: '#F59E0B' }} />}
                                                        {conv.title}
                                                    </div>
                                                )}
                                                <div style={{ fontSize: 10, color: '#475569', marginTop: 2 }}>
                                                    {conv.message_count} 条消息 · {formatTime(conv.updated_at)}
                                                </div>
                                            </div>
                                            <div style={{ display: 'flex', gap: 2, alignItems: 'center', marginLeft: 4 }}>
                                                <Tooltip title={conv.pinned ? '取消置顶' : '置顶'}>
                                                    <Button
                                                        type="text"
                                                        size="small"
                                                        icon={conv.pinned ? <PushpinFilled style={{ fontSize: 11, color: '#F59E0B' }} /> : <PushpinOutlined style={{ fontSize: 11 }} />}
                                                        onClick={(e) => { e.stopPropagation(); togglePin(conv.id, !!conv.pinned) }}
                                                        style={{ color: conv.pinned ? '#F59E0B' : '#64748B', padding: '0 4px', height: 24 }}
                                                    />
                                                </Tooltip>
                                                <Tooltip title="导出">
                                                    <Button
                                                        type="text"
                                                        size="small"
                                                        icon={<DownloadOutlined style={{ fontSize: 11 }} />}
                                                        onClick={(e) => { e.stopPropagation(); exportConversation(conv.id) }}
                                                        style={{ color: '#64748B', padding: '0 4px', height: 24 }}
                                                    />
                                                </Tooltip>
                                                <Tooltip title="重命名">
                                                    <Button
                                                        type="text"
                                                        size="small"
                                                        icon={<EditOutlined style={{ fontSize: 11 }} />}
                                                        onClick={(e) => {
                                                            e.stopPropagation()
                                                            setEditingTitle(conv.id)
                                                        }}
                                                        style={{ color: '#64748B', padding: '0 4px', height: 24 }}
                                                    />
                                                </Tooltip>
                                                <Tooltip title="删除">
                                                    <Button
                                                        type="text"
                                                        size="small"
                                                        icon={<DeleteOutlined style={{ fontSize: 11 }} />}
                                                        onClick={(e) => {
                                                            e.stopPropagation()
                                                            Modal.confirm({
                                                                title: '确定删除此对话？',
                                                                content: `"${conv.title}" 将被永久删除。`,
                                                                okText: '删除',
                                                                okType: 'danger',
                                                                cancelText: '取消',
                                                                onOk: () => deleteConversation(conv.id),
                                                            })
                                                        }}
                                                        style={{ color: '#EF4444', padding: '0 4px', height: 24 }}
                                                    />
                                                </Tooltip>
                                            </div>
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </>
                )}
            </div>

            {/* Main Chat Area */}
            <div
                style={{
                    flex: 1,
                    display: 'flex',
                    flexDirection: 'column',
                    minWidth: 0,
                }}
            >
                {/* Header */}
                <div
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '10px 16px',
                        borderBottom: '1px solid rgba(148,163,184,0.12)',
                        background: 'rgba(15,23,42,0.8)',
                        backdropFilter: 'blur(10px)',
                    }}
                >
                    <Space size={10}>
                        <Button
                            type="text"
                            icon={sidebarOpen ? <MenuFoldOutlined /> : <MenuUnfoldOutlined />}
                            onClick={() => setSidebarOpen(!sidebarOpen)}
                            style={{ color: '#64748B' }}
                        />
                        <RobotOutlined style={{ fontSize: 16, color: '#8B5CF6' }} />
                        <span style={{ fontWeight: 600, fontSize: 14, letterSpacing: 0.3 }}>
                            {activeConversation ? activeConversation.title : '天机灵境对话'}
                        </span>
                        {activeConversation && activeConversation.summary && (
                            <Tooltip title={activeConversation.summary}>
                                <Tag
                                    color="purple"
                                    style={{
                                        fontSize: 10,
                                        maxWidth: 150,
                                        overflow: 'hidden',
                                        textOverflow: 'ellipsis',
                                        whiteSpace: 'nowrap',
                                    }}
                                >
                                    <FileTextOutlined /> 摘要
                                </Tag>
                            </Tooltip>
                        )}
                        <span
                            style={{
                                fontSize: 11,
                                color: '#64748B',
                                background: 'rgba(139,92,246,0.12)',
                                padding: '1px 8px',
                                borderRadius: 10,
                            }}
                        >
                            ICME-T · Lingjing v1.0
                        </span>
                        {/* ✅ v9.1融合: Agent切换指示器 */}
                        <Tooltip title={`当前Agent: ${currentAgent.name} (${currentAgent.layer}) · ${currentAgent.role}`}>
                            <Tag
                                style={{
                                    fontSize: 11,
                                    background: 'rgba(245,158,11,0.12)',
                                    border: '1px solid rgba(245,158,11,0.3)',
                                    color: '#F59E0B',
                                    cursor: 'pointer',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 4,
                                }}
                            >
                                <SwapOutlined style={{ fontSize: 10 }} />
                                {currentAgent.emoji} {currentAgent.name}
                            </Tag>
                        </Tooltip>
                        {/* ✅ v9.1融合: 系统状态指示 */}
                        <Tooltip title={`MCP: ${fusionHealth.mcp_bridge ? '✅' : '❌'} | Skill: ${fusionHealth.skill_resolver ? '✅' : '❌'} | Agent: ${fusionHealth.agent_broker ? '✅' : '❌'}`}>
                            <Tag
                                style={{
                                    fontSize: 9,
                                    background: fusionHealth.mcp_bridge && fusionHealth.agent_broker
                                        ? 'rgba(16,185,129,0.12)'
                                        : 'rgba(239,68,68,0.12)',
                                    border: `1px solid ${fusionHealth.mcp_bridge && fusionHealth.agent_broker
                                        ? 'rgba(16,185,129,0.3)'
                                        : 'rgba(239,68,68,0.3)'}`,
                                    color: fusionHealth.mcp_bridge && fusionHealth.agent_broker ? '#10B981' : '#EF4444',
                                }}
                            >
                                <TeamOutlined style={{ fontSize: 9 }} /> 融合
                            </Tag>
                        </Tooltip>
                    </Space>
                    <Space size={6}>
                        {tokenCount > 0 && (
                            <span
                                style={{
                                    fontSize: 10,
                                    color: tokenCount > 12000 ? '#F59E0B' : '#475569',
                                    fontFamily: 'monospace',
                                    background: 'rgba(148,163,184,0.06)',
                                    padding: '2px 8px',
                                    borderRadius: 10,
                                }}
                            >
                                {tokenCount.toLocaleString()} tokens
                            </span>
                        )}
                        <Tooltip title="🧠 记忆操作中心 (存储/提取/推送/调度)">
                            <Button
                                type="primary"
                                icon={<DatabaseOutlined />}
                                onClick={() => setMemoryPanelOpen(true)}
                                size="small"
                                style={{ background: 'linear-gradient(135deg, #8B5CF6, #7C3AED)', border: 'none' }}
                            >
                                记忆中心
                            </Button>
                        </Tooltip>
                        <Tooltip title="Clear current view">
                            <Button
                                type="text"
                                icon={<ClearOutlined />}
                                onClick={handleClear}
                                size="small"
                                style={{ color: '#64748B' }}
                            />
                        </Tooltip>
                    </Space>
                </div>

                {/* Messages */}
                <div
                    style={{
                        flex: 1,
                        overflowY: 'auto',
                        padding: '16px 20px',
                        scrollBehavior: 'smooth',
                    }}
                >
                    {offlineMode && (
                        <div
                            style={{
                                background: 'rgba(250,173,20,0.12)',
                                border: '1px solid rgba(250,173,20,0.25)',
                                borderRadius: 8,
                                padding: '6px 12px',
                                marginBottom: 12,
                                display: 'flex',
                                alignItems: 'center',
                                gap: 8,
                                fontSize: 12,
                                color: '#F59E0B',
                            }}
                        >
                            <DatabaseOutlined />
                            <span>离线模式 — 消息已保存到本地IndexedDB，恢复连接后自动同步</span>
                        </div>
                    )}
                    {messages.length === 0 && (
                        <div
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                height: '100%',
                                flexDirection: 'column',
                                gap: 12,
                            }}
                        >
                            <RobotOutlined style={{ fontSize: 48, color: '#334155' }} />
                            <span style={{ color: '#475569', fontSize: 14 }}>与天机AI开始对话</span>
                            <span style={{ color: '#334155', fontSize: 12, maxWidth: 400, textAlign: 'center' }}>
                                基于ICME-T记忆架构 · AFM上下文管理 · 多轮对话·工具调用·安全护栏
                            </span>
                            {/* ✅ v9.1 UX优化: 期望管理 - 首次进入显示能力说明 */}
                            {showWelcome && (
                                <div style={{
                                    marginTop: 12,
                                    padding: '12px 16px',
                                    background: 'rgba(139,92,246,0.06)',
                                    border: '1px solid rgba(139,92,246,0.15)',
                                    borderRadius: 10,
                                    maxWidth: 460,
                                    textAlign: 'left',
                                    fontSize: 12,
                                    color: '#94A3B8',
                                    lineHeight: 1.8,
                                }}>
                                    <div style={{ color: '#C4B5FD', fontWeight: 500, marginBottom: 4 }}>
                                        <BulbOutlined style={{ marginRight: 4 }} />天机可以帮你:
                                    </div>
                                    <div>- 搜索、存储、管理你的记忆和知识</div>
                                    <div>- 调度专业Agent处理复杂任务 (代码审查/写作/运维)</div>
                                    <div>- 分析文本分类、提取知识、生成摘要</div>
                                    <div>- 查看系统状态、管理对话历史</div>
                                    <div style={{ marginTop: 4, color: '#64748B', fontSize: 11 }}>
                                        提示: 对话可能不完全准确，重要信息请核实。输入 /help 查看更多命令。
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {messages.map((msg) => (
                        <div
                            key={msg.id}
                            style={{
                                marginBottom: 16,
                                maxWidth: 900,
                                marginLeft: msg.role === 'assistant' ? 0 : 'auto',
                                marginRight: msg.role === 'user' ? 0 : 'auto',
                            }}
                        >
                            <div
                                style={{
                                    display: 'flex',
                                    gap: 10,
                                    alignItems: 'flex-start',
                                }}
                            >
                                <Avatar
                                    size={28}
                                    icon={msg.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
                                    style={{
                                        background:
                                            msg.role === 'user'
                                                ? 'linear-gradient(135deg, #3B82F6, #2563EB)'
                                                : 'linear-gradient(135deg, #8B5CF6, #7C3AED)',
                                        flexShrink: 0,
                                        marginTop: 2,
                                    }}
                                />

                                <div style={{ flex: 1, minWidth: 0 }}>
                                    <div
                                        style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: 8,
                                            marginBottom: 4,
                                            fontSize: 11,
                                            color: '#94A3B8',
                                        }}
                                    >
                                        <span style={{ fontWeight: 600 }}>{msg.role === 'user' ? '用户' : '天机'}</span>
                                        {msg.isStreaming && (
                                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                                                <LoadingOutlined spin style={{ fontSize: 10, color: '#8B5CF6' }} />
                                                <span style={{ color: '#8B5CF6' }}>生成中...</span>
                                            </span>
                                        )}
                                        {!msg.isStreaming && msg.timestamp && (
                                            <span>{new Date(msg.timestamp).toLocaleTimeString()}</span>
                                        )}
                                        {msg.tokenCount !== undefined && msg.tokenCount > 0 && (
                                            <span style={{ color: '#475569', fontFamily: 'monospace', fontSize: 9 }}>
                                                ~{msg.tokenCount}t
                                            </span>
                                        )}
                                        {msg.fidelity && msg.fidelity !== 'full' && (
                                            <Tag style={{ fontSize: 9, lineHeight: '16px', padding: '0 4px' }}>
                                                {msg.fidelity}
                                            </Tag>
                                        )}
                                        {/* ✅ DeepSeek: 模型模式标签 */}
                                        {msg.role === 'assistant' && msg.modelMode && (
                                            <Tag
                                                style={{
                                                    fontSize: 9,
                                                    lineHeight: '16px',
                                                    padding: '0 6px',
                                                    background: msg.modelMode === 'v4-pro' ? 'rgba(245,158,11,0.12)' : 'rgba(16,185,129,0.12)',
                                                    border: `1px solid ${msg.modelMode === 'v4-pro' ? 'rgba(245,158,11,0.3)' : 'rgba(16,185,129,0.3)'}`,
                                                    color: msg.modelMode === 'v4-pro' ? '#F59E0B' : '#10B981',
                                                }}
                                            >
                                                {msg.modelMode === 'v4-pro' ? <BulbOutlined /> : <ThunderboltOutlined />}
                                                {' '}{msg.modelMode === 'v4-pro' ? 'V4-Pro' : 'V4-Flash'}
                                            </Tag>
                                        )}
                                        {/* ✅ DeepSeek: Thinking模式标签 */}
                                        {msg.role === 'assistant' && msg.thinkingEnabled && (
                                            <Tag
                                                style={{
                                                    fontSize: 9,
                                                    lineHeight: '16px',
                                                    padding: '0 6px',
                                                    background: 'rgba(139,92,246,0.12)',
                                                    border: '1px solid rgba(139,92,246,0.3)',
                                                    color: '#A78BFA',
                                                }}
                                            >
                                                🧠 Thinking
                                            </Tag>
                                        )}
                                        {/* ✅ DeepSeek: 已编辑标签 */}
                                        {msg.isEdited && (
                                            <Tag
                                                style={{
                                                    fontSize: 9,
                                                    lineHeight: '16px',
                                                    padding: '0 6px',
                                                    background: 'rgba(148,163,184,0.08)',
                                                    border: '1px solid rgba(148,163,184,0.2)',
                                                    color: '#94A3B8',
                                                }}
                                            >
                                                已编辑
                                            </Tag>
                                        )}
                                    </div>

                                    {msg.role === 'assistant' && msg.opEvents && msg.opEvents.length > 0 && (
                                        <OperationTransparencyInline events={msg.opEvents} compact={true} />
                                    )}

                                    {/* ✅ DeepSeek: 推理过程显示 (可折叠) */}
                                    {msg.role === 'assistant' && msg.reasoningContent && msg.reasoningContent.trim() && (
                                        <div
                                            style={{
                                                marginBottom: 6,
                                                background: 'rgba(139,92,246,0.06)',
                                                border: '1px solid rgba(139,92,246,0.2)',
                                                borderRadius: 8,
                                                overflow: 'hidden',
                                            }}
                                        >
                                            <div
                                                onClick={() => toggleReasoningExpand(msg.id)}
                                                style={{
                                                    padding: '6px 12px',
                                                    cursor: 'pointer',
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    justifyContent: 'space-between',
                                                    fontSize: 11,
                                                    color: '#A78BFA',
                                                    background: 'rgba(139,92,246,0.04)',
                                                }}
                                            >
                                                <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                                    <BulbOutlined style={{ fontSize: 11 }} />
                                                    推理过程 {msg.isStreaming && '(生成中...)'}
                                                </span>
                                                <span style={{ fontSize: 10, color: '#64748B' }}>
                                                    {expandedReasoning.has(msg.id) ? '收起 ▲' : '展开 ▼'}
                                                </span>
                                            </div>
                                            {expandedReasoning.has(msg.id) && (
                                                <div
                                                    style={{
                                                        padding: '8px 12px',
                                                        fontSize: 12,
                                                        color: '#94A3B8',
                                                        lineHeight: 1.6,
                                                        maxHeight: 300,
                                                        overflowY: 'auto',
                                                        whiteSpace: 'pre-wrap',
                                                        borderTop: '1px solid rgba(139,92,246,0.15)',
                                                    }}
                                                >
                                                    {msg.reasoningContent}
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    <div
                                        style={{
                                            background:
                                                msg.role === 'user' ? 'rgba(59,130,246,0.08)' : 'rgba(30,41,59,0.6)',
                                            borderRadius: 10,
                                            padding: '12px 16px',
                                            border:
                                                msg.role === 'user'
                                                    ? '1px solid rgba(59,130,246,0.15)'
                                                    : '1px solid rgba(148,163,184,0.1)',
                                            lineHeight: 1.7,
                                            fontSize: 13.5,
                                            wordBreak: 'break-word',
                                        }}
                                    >
                                        {msg.role === 'assistant' ? (
                                            <ReactMarkdown>{msg.content || (msg.isStreaming ? '▌' : '')}</ReactMarkdown>
                                        ) : (
                                            <span style={{ color: '#E2E8F0' }}>{msg.content}</span>
                                        )}
                                    </div>

                                    {/* ✅ DeepSeek: 消息操作按钮组 (hover显示) */}
                                    {msg.content && !msg.isStreaming && (
                                        <div
                                            style={{
                                                display: 'flex',
                                                gap: 4,
                                                marginTop: 6,
                                                justifyContent: 'flex-end',
                                                opacity: 0.7,
                                                transition: 'opacity 0.15s',
                                            }}
                                            onMouseEnter={(e) => {
                                                (e.currentTarget as HTMLDivElement).style.opacity = '1'
                                            }}
                                            onMouseLeave={(e) => {
                                                (e.currentTarget as HTMLDivElement).style.opacity = '0.7'
                                            }}
                                        >
                                            <Tooltip title={copiedId === msg.id ? '已复制!' : '复制'}>
                                                <Button
                                                    type="text"
                                                    size="small"
                                                    icon={copiedId === msg.id ? <CheckOutlined /> : <CopyOutlined />}
                                                    onClick={() => handleCopy(msg.content, msg.id)}
                                                    style={{
                                                        color: copiedId === msg.id ? '#34D399' : '#64748B',
                                                        fontSize: 11,
                                                    }}
                                                />
                                            </Tooltip>
                                            {/* 编辑按钮 - 用户和AI消息都可编辑 */}
                                            <Tooltip title="编辑消息">
                                                <Button
                                                    type="text"
                                                    size="small"
                                                    icon={<EditOutlined />}
                                                    onClick={() => openEditModal(msg)}
                                                    style={{ color: '#64748B', fontSize: 11 }}
                                                />
                                            </Tooltip>
                                            {/* 重新生成按钮 - 仅AI消息 */}
                                            {msg.role === 'assistant' && (
                                                <Tooltip title="重新生成">
                                                    <Button
                                                        type="text"
                                                        size="small"
                                                        icon={
                                                            regeneratingId === msg.id ? (
                                                                <LoadingOutlined spin />
                                                            ) : (
                                                                <ReloadOutlined />
                                                            )
                                                        }
                                                        onClick={() => handleRegenerateMessage(msg)}
                                                        disabled={regeneratingId === msg.id}
                                                        style={{ color: '#64748B', fontSize: 11 }}
                                                    />
                                                </Tooltip>
                                            )}
                                            {/* 删除按钮 */}
                                            <Popconfirm
                                                title="确定删除此消息？"
                                                okText="删除"
                                                okType="danger"
                                                cancelText="取消"
                                                onConfirm={() => handleDeleteMessage(msg.id)}
                                            >
                                                <Tooltip title="删除">
                                                    <Button
                                                        type="text"
                                                        size="small"
                                                        icon={<DeleteOutlined />}
                                                        style={{ color: '#EF4444', fontSize: 11 }}
                                                    />
                                                </Tooltip>
                                            </Popconfirm>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))}

                    <div ref={messagesEndRef} />
                </div>

                {/* Input Area */}
                <div
                    style={{
                        padding: '12px 20px 16px',
                        borderTop: '1px solid rgba(148,163,184,0.12)',
                        background: 'rgba(15,23,42,0.8)',
                        backdropFilter: 'blur(10px)',
                    }}
                >
                    {/* ✅ DeepSeek: V4-Pro/V4-Flash 模式切换 + Thinking + 法则提示词 */}
                    <div
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 12,
                            maxWidth: 900,
                            margin: '0 auto 8px',
                            padding: '6px 10px',
                            background: 'rgba(30,41,59,0.4)',
                            border: '1px solid rgba(148,163,184,0.1)',
                            borderRadius: 8,
                            flexWrap: 'wrap',
                        }}
                    >
                        <span style={{ fontSize: 11, color: '#94A3B8', fontWeight: 500 }}>模型:</span>
                        <Segmented
                            size="small"
                            value={deepseekSettings.modelMode}
                            onChange={(value: SegmentedValue) => {
                                const newMode = value as ModelMode
                                setDeepseekSettings((prev) => ({
                                    ...prev,
                                    modelMode: newMode,
                                    // 切换到V4-Flash时关闭thinking
                                    thinkingEnabled: newMode === 'v4-pro' ? prev.thinkingEnabled : false,
                                }))
                                if (newMode === 'v4-pro') {
                                    message.info('V4-Pro: 复杂推理模式，支持Thinking', 2)
                                } else {
                                    message.info('V4-Flash: 高性价比模式，响应更快', 2)
                                }
                            }}
                            options={[
                                {
                                    label: (
                                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                                            <ThunderboltOutlined /> V4-Flash
                                        </span>
                                    ),
                                    value: 'v4-flash',
                                },
                                {
                                    label: (
                                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                                            <BulbOutlined /> V4-Pro
                                        </span>
                                    ),
                                    value: 'v4-pro',
                                },
                            ]}
                            style={{
                                background: 'rgba(15,23,42,0.6)',
                            }}
                        />

                        {/* Thinking模式开关 - 仅V4-Pro显示 */}
                        {deepseekSettings.modelMode === 'v4-pro' && (
                            <>
                                <div style={{ width: 1, height: 20, background: 'rgba(148,163,184,0.2)' }} />
                                <span style={{ fontSize: 11, color: '#94A3B8', fontWeight: 500 }}>Thinking:</span>
                                <Switch
                                    size="small"
                                    checked={deepseekSettings.thinkingEnabled}
                                    onChange={(checked) =>
                                        setDeepseekSettings((prev) => ({ ...prev, thinkingEnabled: checked }))
                                    }
                                    checkedChildren="🧠"
                                    unCheckedChildren="关"
                                />
                                {deepseekSettings.thinkingEnabled && (
                                    <Segmented
                                        size="small"
                                        value={deepseekSettings.reasoningEffort}
                                        onChange={(value: SegmentedValue) =>
                                            setDeepseekSettings((prev) => ({
                                                ...prev,
                                                reasoningEffort: value as ReasoningEffort,
                                            }))
                                        }
                                        options={[
                                            { label: 'Low', value: 'low' },
                                            { label: 'Medium', value: 'medium' },
                                            { label: 'High', value: 'high' },
                                        ]}
                                        style={{ background: 'rgba(15,23,42,0.6)' }}
                                    />
                                )}
                                {deepseekSettings.thinkingEnabled && (
                                    <Tooltip title="将输出推理过程，消耗更多token">
                                        <Tag
                                            style={{
                                                fontSize: 9,
                                                background: 'rgba(139,92,246,0.12)',
                                                border: '1px solid rgba(139,92,246,0.3)',
                                                color: '#A78BFA',
                                                padding: '0 6px',
                                            }}
                                        >
                                            推理模式
                                        </Tag>
                                    </Tooltip>
                                )}
                            </>
                        )}

                        <div style={{ width: 1, height: 20, background: 'rgba(148,163,184,0.2)' }} />
                        <span style={{ fontSize: 11, color: '#94A3B8', fontWeight: 500 }}>法则:</span>
                        <Switch
                            size="small"
                            checked={deepseekSettings.useLawPrompt}
                            onChange={(checked) =>
                                setDeepseekSettings((prev) => ({ ...prev, useLawPrompt: checked }))
                            }
                            checkedChildren="注入"
                            unCheckedChildren="关"
                        />
                        {deepseekSettings.useLawPrompt && (
                            <Tooltip title="已注入天机法则+常识系统提示词">
                                <Tag
                                    style={{
                                        fontSize: 9,
                                        background: 'rgba(16,185,129,0.12)',
                                        border: '1px solid rgba(16,185,129,0.3)',
                                        color: '#10B981',
                                        padding: '0 6px',
                                    }}
                                >
                                    ⚖️ 天机法则
                                </Tag>
                            </Tooltip>
                        )}
                    </div>

                    {/* ✅ v9.1融合: Skill推荐 + 建议回复 */}
                    {skillSuggestions.length > 0 && (
                        <div style={{
                            display: 'flex',
                            gap: 6,
                            marginBottom: 8,
                            flexWrap: 'wrap',
                            maxWidth: 900,
                            margin: '0 auto 8px',
                        }}>
                            <BulbOutlined style={{ color: '#8B5CF6', fontSize: 12, marginTop: 4 }} />
                            {skillSuggestions.map((suggestion, idx) => (
                                <Tag
                                    key={idx}
                                    style={{
                                        fontSize: 11,
                                        background: 'rgba(139,92,246,0.08)',
                                        border: '1px solid rgba(139,92,246,0.2)',
                                        color: '#C4B5FD',
                                        cursor: 'pointer',
                                        borderRadius: 12,
                                        padding: '2px 10px',
                                        transition: 'all 0.15s',
                                    }}
                                    onClick={() => {
                                        setInput(suggestion)
                                        setSkillSuggestions([])
                                    }}
                                >
                                    {suggestion}
                                </Tag>
                            ))}
                            <Tag
                                style={{
                                    fontSize: 10,
                                    background: 'transparent',
                                    border: '1px solid rgba(148,163,184,0.1)',
                                    color: '#64748B',
                                    cursor: 'pointer',
                                    borderRadius: 12,
                                    padding: '2px 8px',
                                }}
                                onClick={() => setSkillSuggestions([])}
                            >
                                ✕
                            </Tag>
                        </div>
                    )}
                    {/* ✅ v9.1融合: 工具调用结果条 */}
                    {toolCallResults.length > 0 && (
                        <div style={{
                            display: 'flex',
                            gap: 4,
                            marginBottom: 6,
                            maxWidth: 900,
                            margin: '0 auto 6px',
                            overflowX: 'auto',
                        }}>
                            {toolCallResults.slice(-3).map((tc, idx) => (
                                <Tag
                                    key={idx}
                                    style={{
                                        fontSize: 9,
                                        background: 'rgba(16,185,129,0.08)',
                                        border: '1px solid rgba(16,185,129,0.2)',
                                        color: '#6EE7B7',
                                        borderRadius: 8,
                                        maxWidth: 200,
                                        overflow: 'hidden',
                                        textOverflow: 'ellipsis',
                                        whiteSpace: 'nowrap',
                                    }}
                                >
                                    <ThunderboltOutlined style={{ fontSize: 8 }} /> {tc.toolName}
                                </Tag>
                            ))}
                        </div>
                    )}
                    <div
                        style={{
                            display: 'flex',
                            gap: 10,
                            alignItems: 'flex-end',
                            maxWidth: 900,
                            margin: '0 auto',
                        }}
                    >
                        <div style={{ flex: 1 }}>
                            <TextArea
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={handleKeyDown}
                                placeholder="输入消息... (Enter发送, Shift+Enter换行, Esc停止)"
                                autoSize={{ minRows: 1, maxRows: 6 }}
                                disabled={loading}
                                style={{
                                    background: 'rgba(30,41,59,0.6)',
                                    border: '1px solid rgba(148,163,184,0.15)',
                                    color: '#E2E8F0',
                                    borderRadius: 10,
                                    fontSize: 13.5,
                                    resize: 'none',
                                }}
                            />
                            <div
                                style={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center',
                                    marginTop: 4,
                                    padding: '0 4px',
                                }}
                            >
                                <span style={{ fontSize: 10, color: '#475569' }}>
                                    上下文窗口: {tokenCount > 12000 ? '⚠️ 接近上限' : '✅ 空间充足'}
                                </span>
                                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                                    {/* ✅ v9.1 UX优化: 快捷建议 */}
                                    {!loading && messages.length === 0 && (
                                        <>
                                            <Tag
                                                style={{ fontSize: 10, cursor: 'pointer', background: 'rgba(139,92,246,0.08)', border: '1px solid rgba(139,92,246,0.15)', color: '#A78BFA', borderRadius: 10 }}
                                                onClick={() => setInput('搜索我的记忆')}
                                            >
                                                <SearchOutlined style={{ fontSize: 9 }} /> 搜索记忆
                                            </Tag>
                                            <Tag
                                                style={{ fontSize: 10, cursor: 'pointer', background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.15)', color: '#93C5FD', borderRadius: 10 }}
                                                onClick={() => setInput('帮我记住这段内容')}
                                            >
                                                <DatabaseOutlined style={{ fontSize: 9 }} /> 存储记忆
                                            </Tag>
                                            <Tag
                                                style={{ fontSize: 10, cursor: 'pointer', background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.15)', color: '#FCD34D', borderRadius: 10 }}
                                                onClick={() => setInput('调度专家Agent帮我分析')}
                                            >
                                                <TeamOutlined style={{ fontSize: 9 }} /> Agent调度
                                            </Tag>
                                        </>
                                    )}
                                    <span style={{ fontSize: 10, color: '#334155' }}>
                                        {input.length > 0 && `${input.length}字 · `}
                                        {conversationId ? `会话: ${conversationId.slice(-12)}` : '新会话'}
                                    </span>
                                </div>
                            </div>
                        </div>
                        {loading ? (
                            <Tooltip title="Stop (Esc)">
                                <Button
                                    icon={<StopOutlined />}
                                    onClick={handleAbort}
                                    danger
                                    type="primary"
                                    style={{
                                        borderRadius: 10,
                                        height: 40,
                                        width: 40,
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                    }}
                                />
                            </Tooltip>
                        ) : (
                            <Tooltip title="Send (Enter)">
                                <Button
                                    icon={<SendOutlined />}
                                    onClick={handleSend}
                                    disabled={!input.trim()}
                                    type="primary"
                                    style={{
                                        borderRadius: 10,
                                        height: 40,
                                        width: 40,
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        background: input.trim()
                                            ? 'linear-gradient(135deg, #8B5CF6, #7C3AED)'
                                            : undefined,
                                        border: 'none',
                                    }}
                                />
                            </Tooltip>
                        )}
                    </div>
                </div>
            </div>

            {/* ✅ DeepSeek: 消息编辑Modal */}
            <Modal
                title={
                    <Space>
                        <EditOutlined />
                        <span>编辑消息</span>
                        {editingMessage?.role === 'assistant' && (
                            <Tag color="purple" style={{ fontSize: 10 }}>AI回复</Tag>
                        )}
                        {editingMessage?.role === 'user' && (
                            <Tag color="blue" style={{ fontSize: 10 }}>用户消息</Tag>
                        )}
                    </Space>
                }
                open={!!editingMessage}
                onOk={() => editingMessage && handleEditMessage(editingMessage)}
                onCancel={cancelEdit}
                okText="保存"
                cancelText="取消"
                width={600}
                destroyOnClose
            >
                <TextArea
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    autoSize={{ minRows: 4, maxRows: 12 }}
                    placeholder="编辑消息内容..."
                    style={{
                        background: 'rgba(30,41,59,0.6)',
                        border: '1px solid rgba(148,163,184,0.15)',
                        color: '#E2E8F0',
                        borderRadius: 8,
                    }}
                />
                <div style={{ marginTop: 8, fontSize: 11, color: '#64748B' }}>
                    保存后将调用 PUT API 更新服务端消息，并显示"已编辑"标签
                </div>
            </Modal>

            <MemoryOpsPanel visible={memoryPanelOpen} onClose={() => setMemoryPanelOpen(false)} />
        </div>
    )
}
