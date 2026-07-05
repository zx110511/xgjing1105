r"""
EnforcementHookMCP 桥接模块
============================
容器注册用适配层，将 core.enforcement_hook.TianjiEnforcementHook
包装为容器可注册的 EnforcementHookMCP 接口。
"""

import threading
from pathlib import Path
from typing import Optional, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from core.enforcement.enforcement_hook import (
        TianjiEnforcementHook,
        ConversationRegistry,
        ConversationRecord,
        EnforcementDecision,
    )

_hook_instance: Optional["EnforcementHookMCP"] = None
_lock = threading.Lock()


def _lazy_import_hook():
    from core.enforcement.enforcement_hook import (
        TianjiEnforcementHook,
        ConversationRegistry,
        ConversationRecord,
        EnforcementDecision,
    )
    return (TianjiEnforcementHook, ConversationRegistry, ConversationRecord, EnforcementDecision)


def get_enforcement_hook() -> Optional["EnforcementHookMCP"]:
    return _hook_instance


class EnforcementHookMCP:
    def __init__(self, memory_api_url: str = "http://127.0.0.1:8771",
                 local_cache_dir: Optional[Path] = None,
                 event_bus=None):
        _, ConversationRegistry, _, _ = _lazy_import_hook()
        self._registry = ConversationRegistry()
        TianjiEnforcementHook, _, _, _ = _lazy_import_hook()
        self._hook = TianjiEnforcementHook(
            registry=self._registry,
            memory_api_url=memory_api_url,
            local_cache_dir=local_cache_dir,
            event_bus=event_bus,
        )
        self._paused = False
        self._sessions: Dict[str, dict] = {}
        self._session_lock = threading.Lock()

        global _hook_instance
        with _lock:
            _hook_instance = self

    @property
    def enabled(self) -> bool:
        return self._hook.enabled and not self._paused

    def pre_conversation_hook(self, user_input: str, session_id: str,
                               agent_id: str = "", platform: str = "trae"):
        return self._hook.pre_conversation_hook(user_input, session_id, agent_id, platform)

    def post_conversation_hook(self, user_input: str, ai_response: str,
                                session_id: str, agent_id: str = "",
                                turn_number: int = 1, mcp_calls: List[str] = None):
        return self._hook.post_conversation_hook(
            user_input, ai_response, session_id, agent_id, turn_number, mcp_calls,
        )

    def start_session(self, session_id: str, platform: str = "trae", agent_id: str = ""):
        with self._session_lock:
            self._sessions[session_id] = {"platform": platform, "agent_id": agent_id, "turn": 0}
        return {"status": "started", "session_id": session_id}

    def register_turn(self, session_id: str, user_input: str, ai_response: str,
                      mcp_calls: List[str] = None):
        with self._session_lock:
            info = self._sessions.get(session_id, {})
            info["turn"] = info.get("turn", 0) + 1
            self._sessions[session_id] = info
            turn = info["turn"]
            agent_id = info.get("agent_id", "")
            platform = info.get("platform", "trae")
        if turn == 1:
            try:
                self._hook.pre_conversation_hook(user_input, session_id, agent_id, platform)
            except Exception:
                pass
        decision = self._hook.post_conversation_hook(
            user_input, ai_response, session_id,
            agent_id=agent_id, turn_number=turn, mcp_calls=mcp_calls,
        )
        return {
            "status": "recorded" if decision.should_record else "skipped",
            "session_id": session_id,
            "turn_number": turn,
            "layer": decision.target_layer,
            "priority": decision.priority,
        }

    def complete_session(self, session_id: str, force_record: bool = True):
        with self._session_lock:
            info = self._sessions.pop(session_id, None)
        if info and force_record:
            self._hook.flush_pending()
        try:
            self._hook.transition_vcon_lifecycle(session_id, "completed", "session_completed")
        except Exception:
            pass
        return {"status": "completed", "session_id": session_id}

    def flush_pending(self) -> int:
        return self._hook.flush_pending()

    def get_stats(self) -> Dict:
        return self._hook.get_stats()

    def get_compliance(self) -> Dict:
        return self._hook.check_compliance()

    def check_health(self) -> Dict:
        return self._hook.check_compliance()

    def pause(self):
        self._paused = True
        return {"status": "paused"}

    def resume(self):
        self._paused = False
        return {"status": "resumed"}

    def enable(self):
        self._hook.enable()

    def disable(self):
        self._hook.disable()

    def get_nudge_message(self) -> Optional[str]:
        return self._hook.get_nudge_message()

    def register_file_operation(self, session_id: str, operation: str, path: str,
                                 lines_changed: Optional[Dict[str, int]] = None,
                                 reason: str = "",
                                 content_before: str = "",
                                 content_after: str = "",
                                 file_size: int = 0):
        self._hook.register_file_operation(
            session_id, operation, path, lines_changed, reason,
            content_before=content_before, content_after=content_after, file_size=file_size,
        )

    def prepare_file_write(self, session_id: str, path: str, reason: str = "") -> Dict:
        try:
            from pathlib import Path as _P
            fp = _P(path)
            if fp.exists():
                content_before = fp.read_text(encoding="utf-8", errors="replace")
                file_size = fp.stat().st_size
                return {"session_id": session_id, "path": path, "reason": reason,
                        "content_before": content_before[:50000], "file_size": file_size}
            return {"session_id": session_id, "path": path, "reason": reason,
                    "content_before": "", "file_size": 0}
        except Exception:
            return {"session_id": session_id, "path": path, "reason": reason,
                    "content_before": "", "file_size": 0}

    def finalize_file_write(self, session_id: str, path: str, operation: str = "write",
                            reason: str = "", content_before: str = "",
                            content_before_size: int = 0) -> Dict:
        try:
            from pathlib import Path as _P
            fp = _P(path)
            if fp.exists():
                content_after = fp.read_text(encoding="utf-8", errors="replace")
                file_size = fp.stat().st_size
            else:
                content_after = ""
                file_size = 0

            lines_changed = {"added": content_after.count("\n"), "deleted": 0}
            if content_before:
                lines_changed["deleted"] = content_before.count("\n")

            self.register_file_operation(
                session_id=session_id, operation=operation, path=path,
                lines_changed=lines_changed, reason=reason,
                content_before=content_before,
                content_after=content_after[:50000],
                file_size=file_size,
            )
            return {"status": "captured", "session_id": session_id, "path": path,
                    "operation": operation, "file_size": file_size}
        except Exception as e:
            return {"status": "error", "session_id": session_id, "path": path,
                    "error": str(e)}

    def register_error(self, session_id: str, error_type: str, message: str,
                       context: str = ""):
        self._hook.register_error(session_id, error_type, message, context)

    def register_mcp_call(self, session_id: str, tool_name: str,
                           params_summary: str = "", result_summary: str = "",
                           duration_ms: float = 0.0, status: str = "success"):
        self._hook.register_mcp_call(session_id, tool_name, params_summary, result_summary,
                                       duration_ms, status)

    def register_agent_switch(self, session_id: str, source_agent: str,
                               target_agent: str, task_type: str, context_brief: str = ""):
        self._hook.register_agent_switch(session_id, source_agent, target_agent, task_type, context_brief)

    def set_session_agent(self, session_id: str, agent_id: str):
        self._hook.set_session_agent(session_id, agent_id)

    def get_otel_stats(self) -> Dict:
        return self._hook.get_otel_stats()

    def get_otel_recent_spans(self, limit: int = 20) -> List[Dict]:
        return self._hook.get_otel_recent_spans(limit)

    def intercept_workflow(self, workflow_name: str, phase: str,
                           session_id: str = "", agent_id: str = "") -> Dict:
        span = self._hook._otel_interceptor.intercept_workflow(
            workflow_name, phase, session_id, agent_id)
        return span.to_otel_dict()

    def update_vcon_lifecycle(self, session_id: str, new_state: str, reason: str = "") -> Dict:
        return self._hook.transition_vcon_lifecycle(session_id, new_state, reason)

    def record_reasoning(self, session_id: str, chain_id: str, steps: List[Dict] = None,
                         conclusion: str = "", confidence: float = 0.0, duration_ms: float = 0.0):
        self._hook.record_reasoning(session_id, chain_id, steps or [], conclusion, confidence, duration_ms)

    def record_state_change(self, session_id: str, entity_id: str, state_type: str,
                            old_state: str, new_state: str, trigger: str = "",
                            metadata: Dict = None):
        self._hook.record_state_change(session_id, entity_id, state_type, old_state, new_state,
                                        trigger, metadata)

    def record_token_usage(self, session_id: str, prompt_tokens: int = 0,
                           completion_tokens: int = 0, model: str = "deepseek-chat"):
        self._hook.record_token_usage(session_id, prompt_tokens, completion_tokens, model)

    def receive_consumer_feedback(self, source_module: str, feedback_type: str,
                                   content: str, severity: str = "info") -> Dict:
        fb = self._hook.receive_consumer_feedback(source_module, feedback_type, content, severity)
        return fb.to_dict()

    def process_feedback_queue(self) -> Dict:
        return self._hook.process_feedback_queue()

    def get_feedback_stats(self) -> Dict:
        return self._hook.get_feedback_loop_stats()

    def get_seven_dim_stats(self) -> Dict:
        return self._hook.get_seven_dim_stats()

    def check_loongsuite_compliance(self, session_id: str = "") -> Dict:
        return self._hook.check_loongsuite_compliance()

    def trigger_learning_loop(self, session_id: str, force: bool = False) -> Dict:
        return self._hook.trigger_learning_loop(session_id, force)

    def broadcast_evolution_signal(self, signal_type: str, source: str = "",
                                    payload: Dict = None, priority: str = "medium") -> Dict:
        return self._hook.broadcast_evolution_signal(signal_type, source, payload, priority)

    def adaptive_degradation_check(self) -> Dict:
        return self._hook.adaptive_degradation_check()

    def smart_memory_migrate(self, session_id: str) -> Dict:
        return self._hook.smart_memory_migrate(session_id)

    def priority_event_route(self, events: List[Dict]) -> Dict:
        return self._hook.priority_event_route(events)

    def aos_instrument(self, event_type: str, source: str = "",
                       payload: Dict = None, severity: str = "info"):
        self._hook.record_aos_instrument(event_type, source, payload, severity)

    def aos_trace(self, event_type: str, source: str = "",
                  target: str = "", payload: Dict = None):
        self._hook.record_aos_trace(event_type, source, target, payload)

    def aos_inspect(self, event_type: str, source: str = "",
                    payload: Dict = None, severity: str = "info"):
        self._hook.record_aos_inspect(event_type, source, payload, severity)

    def aos_stats(self) -> Dict:
        return self._hook.get_aos_stats()

    def eval_quality(self, name: str, score: float, label: str = "",
                     explanation: str = "") -> Dict:
        return self._hook.evaluate_quality(name, score, label, explanation)

    def eval_stats(self) -> Dict:
        return self._hook.get_evaluation_stats()
