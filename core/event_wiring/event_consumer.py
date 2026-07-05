r"""
天机事件消费者 v1.0 — .pending_events.jsonl 自动消费
====================================================
TVP: @天枢(tianshu) → @忆库(yiku) | 任务: 事件消费 | 优先级: P0

功能:
- 守护线程实时监听 .pending_events.jsonl
- 自动消费 CONVERSATION_INPUT / CONVERSATION_OUTPUT / MEMORY_CREATED 事件
- 智能分层: 根据内容特征写入L0-L5对应层
- 错误处理+重试机制 (3次重试, 指数退避)
- 消费位点持久化 (防止重复消费)
- 认知流水线回写 (cognition.json → semantic层)
- 进化历史同步 (evolution_history → L5 meta层)

闭环链路:
  .pending_events.jsonl → EventConsumer.consume() → engine.remember() → KG同步
"""

import json
import time
import threading
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional


class EventConsumer:
    _instance: Optional["EventConsumer"] = None
    _lock = threading.Lock()

    def __init__(self, data_path: Path, engine: Any = None):
        self._data_path = data_path
        self._engine = engine
        self._pending_file = data_path / ".pending_events.jsonl"
        self._cursor_file = data_path / ".pending_cursor.json"
        self._cognition_file = data_path / "cognition.json"
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stats = {
            "consumed": 0,
            "errors": 0,
            "retries": 0,
            "skipped": 0,
            "last_consume_ts": 0.0,
            "by_type": {},
        }
        self._max_retries = 3
        self._retry_base_delay = 1.0
        self._poll_interval = 2.0
        self._cursor_line = 0
        self._load_cursor()

    @classmethod
    def get_instance(cls, data_path: Path = None, engine: Any = None) -> "EventConsumer":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    if data_path is None:
                        from ..shared.config import DEFAULT_CONFIG
                        data_path = DEFAULT_CONFIG.data_path
                    cls._instance = cls(data_path, engine)
        return cls._instance

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._consume_loop,
            daemon=True,
            name="TianjiEventConsumer",
        )
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._save_cursor()

    def _load_cursor(self):
        try:
            if self._cursor_file.exists():
                data = json.loads(self._cursor_file.read_text(encoding="utf-8"))
                self._cursor_line = data.get("line", 0)
        except Exception:
            self._cursor_line = 0

    def _save_cursor(self):
        try:
            self._cursor_file.write_text(
                json.dumps({"line": self._cursor_line, "updated_at": time.time()}),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _consume_loop(self):
        while self._running:
            try:
                consumed = self._consume_batch()
                if consumed == 0:
                    time.sleep(self._poll_interval)
                else:
                    time.sleep(0.1)
            except Exception:
                time.sleep(self._poll_interval)

    def _consume_batch(self, max_lines: int = 50) -> int:
        if not self._pending_file.exists():
            return 0

        consumed = 0
        try:
            with open(str(self._pending_file), "r", encoding="utf-8-sig") as f:
                current_line = 0
                for line in f:
                    current_line += 1
                    if current_line <= self._cursor_line:
                        continue
                    if consumed >= max_lines:
                        break

                    line = line.strip()
                    if not line:
                        self._cursor_line = current_line
                        continue

                    try:
                        event = json.loads(line)
                        self._process_event(event)
                        consumed += 1
                    except json.JSONDecodeError:
                        self._cursor_line = current_line
                        continue
                    except Exception as e:
                        self._stats["errors"] += 1
                        self._cursor_line = current_line

                    self._cursor_line = current_line

            if consumed > 0:
                self._save_cursor()
        except Exception:
            pass

        return consumed

    def _process_event(self, event: Dict):
        event_type = event.get("event_type", "UNKNOWN")
        content = event.get("content", "")
        source = event.get("source", "unknown")
        session_id = event.get("session_id", "")

        if not content or len(content.strip()) < 10:
            self._stats["skipped"] += 1
            return

        layer, tags, priority = self._classify_event(event_type, content, source)

        if self._engine is not None:
            self._remember_with_retry(
                content=content,
                layer=layer,
                tags=tags,
                priority=priority,
                metadata={
                    "source": source,
                    "event_type": event_type,
                    "session_id": session_id,
                    "auto_consumed": True,
                },
            )
        else:
            self._remember_fallback(content, layer, tags, priority, event)

        self._stats["consumed"] += 1
        self._stats["last_consume_ts"] = time.time()
        self._stats["by_type"][event_type] = self._stats["by_type"].get(event_type, 0) + 1

    def _classify_event(self, event_type: str, content: str, source: str) -> tuple:
        tags = [source, "auto_consumed"]
        priority = "medium"
        layer = "working"

        if event_type == "CONVERSATION_INPUT":
            layer = "sensory"
            tags.extend(["conversation", "user_input"])
            priority = "high"
        elif event_type == "CONVERSATION_OUTPUT":
            layer = "working"
            tags.extend(["conversation", "ai_response"])
            priority = "high"

            content_lower = content.lower()
            # [FIX-v9.1-meta-bloat] 禁止自动分类为meta层，防止134K条暴涨
            # 原逻辑: 包含"策略/规则/规范"等关键词 → meta层(priority=critical)
            # 问题: 每次对话的AI响应都包含这些词，导致meta层无限膨胀
            # 修复: 统一降级为semantic或episodic层
            if any(kw in content_lower for kw in ["策略", "规则", "规范", "元认知", "宪法", "律令"]):
                layer = "semantic"  # 改为semantic而非meta
                priority = "high"   # 降低为high而非critical
            elif any(kw in content_lower for kw in ["知识", "概念", "定义", "原理", "架构", "设计"]):
                layer = "semantic"
                priority = "high"
            elif any(kw in content_lower for kw in ["修复", "错误", "异常", "审计", "测试", "bug"]):
                layer = "episodic"
                tags.append("incident")
                priority = "high"
            elif any(kw in content_lower for kw in ["决策", "执行", "调度", "tvp"]):
                layer = "short_term"
                tags.append("decision")
        elif event_type == "MEMORY_CREATED":
            layer = "episodic"
            tags.append("memory_event")
        elif event_type in ("CONSOLIDATION", "PROMOTION"):
            layer = "episodic"
            tags.extend(["consolidation", "lifecycle"])
            priority = "low"

        return layer, tags, priority

    def _remember_with_retry(self, content: str, layer: str, tags: list,
                             priority: str, metadata: dict):
        for attempt in range(self._max_retries):
            try:
                result = self._engine.remember(
                    content=content,
                    layer=layer,
                    tags=tags,
                    priority=priority,
                    metadata=metadata,
                    use_llm=False,
                )
                if result.get("id"):
                    return
            except Exception:
                self._stats["retries"] += 1
                if attempt < self._max_retries - 1:
                    delay = self._retry_base_delay * (2 ** attempt)
                    time.sleep(delay)

    def _remember_fallback(self, content: str, layer: str, tags: list,
                           priority: str, event: dict):
        try:
            layer_dir = self._data_path / layer
            layer_dir.mkdir(parents=True, exist_ok=True)
            import hashlib
            entry_id = hashlib.sha256(
                f"{content}{time.time()}".encode()
            ).hexdigest()[:16]
            entry_data = {
                "id": entry_id,
                "content": content,
                "layer": layer,
                "tags": tags,
                "priority": priority,
                "created_at": event.get("ts", time.time()),
                "last_accessed": time.time(),
                "access_count": 0,
                "effectiveness_score": 0.5,
                "related_ids": [],
                "metadata": {"source": "event_consumer_fallback"},
                "changelog": [],
            }
            entry_file = layer_dir / f"{entry_id}.json"
            entry_file.write_text(
                json.dumps(entry_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def consume_cognition_insights(self):
        if not self._cognition_file.exists():
            return 0

        try:
            data = json.loads(self._cognition_file.read_text(encoding="utf-8-sig"))
            derived_list = data.get("derived", [])
            if not derived_list:
                return 0

            written = 0
            for insight in derived_list:
                content = insight.get("content", "")
                if not content or len(content.strip()) < 20:
                    continue

                evidence_ids = insight.get("evidence_ids", [])
                confidence = insight.get("confidence", 0.5)
                category = insight.get("category", "facts")

                tags = ["derived_insight", f"category:{category}", "cognition_pipeline"]
                priority = "high" if confidence >= 0.7 else "medium"
                metadata = {
                    "source": "cognition_pipeline",
                    "confidence": confidence,
                    "evidence_ids": evidence_ids,
                    "cognitive_level": insight.get("cognitive_level", "explicit"),
                    "auto_backfilled": True,
                }

                if self._engine is not None:
                    try:
                        result = self._engine.remember(
                            content=content,
                            layer="semantic",
                            tags=tags,
                            priority=priority,
                            metadata=metadata,
                            use_llm=False,
                        )
                        if result.get("id"):
                            written += 1
                    except Exception:
                        pass
                else:
                    self._remember_fallback(content, "semantic", tags, priority,
                                            {"ts": insight.get("created_at", time.time())})
                    written += 1

            return written
        except Exception:
            return 0

    def sync_evolution_to_meta(self):
        evo_dir = self._data_path / "evolution_history"
        if not evo_dir.exists():
            return 0

        written = 0
        try:
            import sqlite3
            db_path = evo_dir / "evolution_history.db"
            if not db_path.exists():
                for evo_file in evo_dir.glob("evolution_*.json"):
                    try:
                        evo_data = json.loads(evo_file.read_text(encoding="utf-8"))
                        summary = evo_data.get("summary", "")
                        if not summary or len(summary.strip()) < 20:
                            continue
                        self._write_evolution_to_meta(summary, evo_data, str(evo_file))
                        written += 1
                    except Exception:
                        continue
                return written

            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            try:
                rows = c.execute(
                    "SELECT timestamp, result_json, rules_modified, rules_added, "
                    "architecture_proposals, summary FROM evolution_history "
                    "ORDER BY id DESC LIMIT 100"
                ).fetchall()
            except Exception:
                conn.close()
                return 0

            for row in rows:
                summary = row["summary"] if isinstance(row, dict) else row[5]
                if not summary or len(str(summary).strip()) < 10:
                    continue

                evo_data = {
                    "timestamp": row["timestamp"] if isinstance(row, dict) else row[0],
                    "rules_modified": row["rules_modified"] if isinstance(row, dict) else row[2],
                    "rules_added": row["rules_added"] if isinstance(row, dict) else row[3],
                    "architecture_proposals": row["architecture_proposals"] if isinstance(row, dict) else row[4],
                }
                self._write_evolution_to_meta(str(summary), evo_data, "evolution_history.db")
                written += 1

            conn.close()
        except Exception:
            pass

        return written

    def _write_evolution_to_meta(self, summary: str, evo_data: dict, source: str):
        # [FIX-v9.1-mem-leak] Meta层容量保护: 超过1000条时跳过写入，防止62K条膨胀
        try:
            meta_layer = self._engine._layers.get("meta", {})
            if len(meta_layer) > 1000:
                logger.debug(f"[EventConsumer] Meta层已{len(meta_layer)}条>1000，跳过进化记录写入")
                return
        except Exception:
            pass

        tags = ["evolution", "auto_sync", "meta_sync"]
        priority = "high"
        metadata = {
            "source": "evolution_history_sync",
            "evo_source": source,
            "rules_modified": evo_data.get("rules_modified", 0),
            "rules_added": evo_data.get("rules_added", 0),
            "architecture_proposals": evo_data.get("architecture_proposals", 0),
            "auto_synced": True,
        }

        if self._engine is not None:
            try:
                self._engine.remember(
                    content=f"[进化记录→Meta] {summary}",
                    layer="meta",
                    tags=tags,
                    priority=priority,
                    metadata=metadata,
                    use_llm=False,
                )
            except Exception:
                pass
        else:
            self._remember_fallback(
                f"[进化记录→Meta] {summary}", "meta", tags, priority,
                {"ts": time.time()},
            )

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "cursor_line": self._cursor_line,
            "running": self._running,
            "pending_file_exists": self._pending_file.exists(),
            "cognition_file_exists": self._cognition_file.exists(),
        }


def start_event_consumer(engine: Any = None, data_path: Path = None):
    if data_path is None:
        from ..shared.config import DEFAULT_CONFIG
        data_path = DEFAULT_CONFIG.data_path
    consumer = EventConsumer.get_instance(data_path, engine)
    consumer.start()
    return consumer


def stop_event_consumer():
    consumer = EventConsumer._instance
    if consumer:
        consumer.stop()
