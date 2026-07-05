"""
AI平台适配器 - AI Platform Adapters
让记忆系统主动适配不同AI平台的对话过程
"""

import time
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


@dataclass
class ConversationContext:
    """对话上下文"""
    session_id: str
    platform: str
    user_id: Optional[str] = None
    conversation_history: List[Dict] = field(default_factory=list)
    current_task: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
    
    def add_message(self, role: str, content: str):
        """添加消息到历史"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })
    
    def get_recent_messages(self, limit: int = 10) -> List[Dict]:
        """获取最近的消息"""
        return self.conversation_history[-limit:]


class AIPlatformAdapter(ABC):
    """AI平台适配器基类"""
    
    def __init__(
        self,
        memory_system: Any,
        llm_layer: Any,
        protocol: Any
    ):
        self.memory_system = memory_system
        self.llm_layer = llm_layer
        self.protocol = protocol
        self.sessions: Dict[str, ConversationContext] = {}
        
    @abstractmethod
    async def intercept_user_input(self, user_input: str, context: Dict) -> str:
        """拦截用户输入, 注入记忆上下文"""
        pass
    
    @abstractmethod
    async def intercept_ai_response(self, ai_response: str, context: Dict) -> str:
        """拦截AI响应, 触发记忆存储"""
        pass
    
    def get_or_create_session(self, session_id: str, platform: str) -> ConversationContext:
        """获取或创建会话"""
        if session_id not in self.sessions:
            self.sessions[session_id] = ConversationContext(
                session_id=session_id,
                platform=platform
            )
        return self.sessions[session_id]


class TraeAdapter(AIPlatformAdapter):
    """Trae IDE平台适配器"""
    
    async def intercept_user_input(self, user_input: str, context: Dict) -> str:
        """拦截用户输入, 主动检索相关记忆"""
        
        session_id = context.get("session_id", "default")
        session = self.get_or_create_session(session_id, "trae")
        
        session.add_message("user", user_input)
        
        if not self.llm_layer.is_ready():
            return user_input
        
        try:
            retrieval_strategy = await self.protocol.build_retrieval_strategy(
                query=user_input,
                context={
                    "conversation_history": session.conversation_history,
                    "current_task": session.current_task,
                    **context
                },
                llm_layer=self.llm_layer
            )
            
            relevant_memories = await self._retrieve_memories(
                query=user_input,
                strategy=retrieval_strategy
            )
            
            if relevant_memories:
                memory_context = self._build_memory_context(relevant_memories)
                
                enhanced_input = f"""[记忆上下文 - 自动注入]
{memory_context}

[用户输入]
{user_input}"""
                
                return enhanced_input
            
        except Exception as e:
            print(f"[TraeAdapter] 拦截用户输入失败: {e}")
        
        return user_input
    
    async def intercept_ai_response(self, ai_response: str, context: Dict) -> str:
        """拦截AI响应, 主动存储重要记忆"""
        
        session_id = context.get("session_id", "default")
        session = self.get_or_create_session(session_id, "trae")
        
        session.add_message("assistant", ai_response)
        
        if not self.llm_layer.is_ready():
            return ai_response
        
        try:
            decision = await self.protocol.process_user_input(
                user_input=ai_response,
                context={
                    "conversation_history": session.conversation_history,
                    "current_task": session.current_task,
                    **context
                },
                llm_layer=self.llm_layer
            )
            
            if decision.action.value == "store" and decision.confidence > 0.7:
                memory_id = await self._store_memory(
                    content=ai_response,
                    decision=decision,
                    session=session
                )
                
                if memory_id and self.protocol.config.enable_auto_knowledge_extraction:
                    triples = await self.protocol.extract_knowledge_from_content(
                        content=ai_response,
                        llm_layer=self.llm_layer
                    )
                    
                    if triples:
                        await self._update_knowledge_graph(triples, memory_id)
        
        except Exception as e:
            print(f"[TraeAdapter] 拦截AI响应失败: {e}")
        
        return ai_response
    
    async def _retrieve_memories(self, query: str, strategy: Any) -> List[Dict]:
        """检索记忆"""
        try:
            results = []
            
            for expanded_query in strategy.query_expansion[:3]:
                search_results = self.memory_system.recall(
                    query=expanded_query,
                    layers=strategy.layer_filter,
                    limit=strategy.max_results // len(strategy.query_expansion)
                )
                
                if isinstance(search_results, dict) and "results" in search_results:
                    results.extend(search_results["results"])
            
            seen_ids = set()
            unique_results = []
            for result in results:
                result_id = result.get("id")
                if result_id and result_id not in seen_ids:
                    seen_ids.add(result_id)
                    unique_results.append(result)
            
            return unique_results[:strategy.max_results]
            
        except Exception as e:
            print(f"[TraeAdapter] 检索记忆失败: {e}")
            return []
    
    async def _store_memory(self, content: str, decision: Any, session: ConversationContext) -> Optional[str]:
        """存储记忆"""
        try:
            memory_id = self.memory_system.remember(
                content=content,
                layer=decision.target_layer or "episodic",
                tags=decision.tags or [],
                priority=decision.priority or "medium",
                metadata={
                    "source": "trae_ai_response",
                    "session_id": session.session_id,
                    "platform": "trae",
                    "value_score": decision.value_score,
                    "reasoning": decision.reasoning,
                    "confidence": decision.confidence
                }
            )
            
            return memory_id
            
        except Exception as e:
            print(f"[TraeAdapter] 存储记忆失败: {e}")
            return None
    
    async def _update_knowledge_graph(self, triples: List[Any], source_id: str):
        """更新知识图谱"""
        try:
            for triple in triples:
                self.memory_system.knowledge_graph.add_relation(
                    source=triple.subject,
                    target=triple.object,
                    relation=triple.relation,
                    weight=triple.confidence
                )
                
        except Exception as e:
            print(f"[TraeAdapter] 更新知识图谱失败: {e}")
    
    def _build_memory_context(self, memories: List[Dict]) -> str:
        """构建记忆上下文字符串"""
        if not memories:
            return "无相关记忆"
        
        context_lines = []
        for i, mem in enumerate(memories[:5], 1):
            content = mem.get("content", "")
            if len(content) > 100:
                content = content[:100] + "..."
            
            layer = mem.get("layer", "unknown")
            relevance = mem.get("relevance", 0.0)
            
            context_lines.append(
                f"{i}. [{layer}] {content} (相关度: {relevance:.2f})"
            )
        
        return "\n".join(context_lines)


class VSCodeAdapter(TraeAdapter):
    """VSCode平台适配器"""
    pass


class CursorAdapter(TraeAdapter):
    """Cursor平台适配器"""
    pass


class GenericAdapter(AIPlatformAdapter):
    """通用平台适配器"""
    
    async def intercept_user_input(self, user_input: str, context: Dict) -> str:
        """通用拦截用户输入"""
        return user_input
    
    async def intercept_ai_response(self, ai_response: str, context: Dict) -> str:
        """通用拦截AI响应"""
        return ai_response


class AdapterRegistry:
    """适配器注册表"""
    
    _adapters: Dict[str, type] = {
        "trae": TraeAdapter,
        "vscode": VSCodeAdapter,
        "cursor": CursorAdapter,
        "generic": GenericAdapter,
    }
    
    @classmethod
    def get_adapter(cls, platform: str) -> type:
        """获取适配器类"""
        return cls._adapters.get(platform.lower(), GenericAdapter)
    
    @classmethod
    def register_adapter(cls, platform: str, adapter_class: type):
        """注册适配器"""
        cls._adapters[platform.lower()] = adapter_class
    
    @classmethod
    def list_adapters(cls) -> List[str]:
        """列出所有适配器"""
        return list(cls._adapters.keys())
