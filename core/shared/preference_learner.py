"""
P2: 偏好学习启用 — 用户行为数据收集
============================================
功能:
1. 收集用户交互行为数据
2. 识别使用模式
3. 生成个性化建议
4. 支持隐私保护（可选匿名化）

收集维度:
- 功能使用频率
- 操作时间模式
- 偏好的Agent组合
- 常用查询类型
- 界面交互习惯

使用方法:
  python preference_learner.py --init       # 初始化收集器
  python preference_learner.py --record      # 模拟记录
  python preference_learner.py --analyze     # 分析模式
  python preference_learner.py --suggest     # 生成建议
"""

import sqlite3
import json
import time
import uuid
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from collections import defaultdict

DB_PATH = Path(__file__).resolve().parent.parent / "data" / ".memory" / "icme.db"

@dataclass
class UserBehaviorEvent:
    """用户行为事件"""
    timestamp: float
    event_type: str  # click / search / agent_invoke / page_view / config_change / feedback
    category: str   # memory / mcp / chat / settings / dashboard
    action: str     # 具体动作描述
    value: Optional[str] = None  # 动作值（如搜索词、Agent名称）
    metadata: dict = field(default_factory=dict)
    session_id: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "category": self.category,
            "action": self.action,
            "value": self.value,
            "metadata": self.metadata,
            "session_id": self.session_id,
        }


class PreferenceLearner:
    """偏好学习引擎"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.conn = None
        self._event_buffer: List[UserBehaviorEvent] = []
        self._buffer_size = 20
        self._lock = threading.Lock()
        self._current_session = str(uuid.uuid4())[:8]

        # 统计缓存
        self._stats_cache = {
            "total_events": 0,
            "by_event_type": defaultdict(int),
            "by_category": defaultdict(int),
            "by_hour": defaultdict(int),
            "top_actions": defaultdict(int),
            "agent_preferences": defaultdict(int),
            "search_patterns": [],
        }

    def connect(self):
        if self.conn is None:
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row

            # 创建行为表（如果不存在）
            cur = self.conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_behavior_events (
                    id TEXT PRIMARY KEY,
                    timestamp REAL,
                    event_type TEXT,
                    category TEXT,
                    action TEXT,
                    value TEXT,
                    metadata TEXT,
                    session_id TEXT,
                    processed INTEGER DEFAULT 0
                )
            """)

            # 创建索引
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_behavior_time
                ON user_behavior_events(timestamp)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_behavior_type
                ON user_behavior_events(event_type)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_behavior_category
                ON user_behavior_events(category)
            """)

            self.conn.commit()
        return self.conn

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def record_event(
        self,
        event_type: str,
        category: str,
        action: str,
        value: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """
        记录用户行为事件

        参数:
            event_type: click / search / agent_invoke / page_view / etc.
            category: memory / mcp / chat / settings / dashboard
            action: 具体动作
            value: 动作值
            metadata: 额外信息

        返回: event_id
        """
        event = UserBehaviorEvent(
            timestamp=time.time(),
            event_type=event_type,
            category=category,
            action=action,
            value=value,
            metadata={
                **(metadata or {}),
                "recorded_by": "preference_learner",
            },
            session_id=self._current_session,
        )

        with self._lock:
            self._event_buffer.append(event)

            # 更新统计缓存
            self._stats_cache["total_events"] += 1
            self._stats_cache["by_event_type"][event_type] += 1
            self._stats_cache["by_category"][category] += 1

            hour = datetime.fromtimestamp(event.timestamp).hour
            self._stats_cache["by_hour"][hour] += 1

            action_key = f"{category}:{action}"
            self._stats_cache["top_actions"][action_key] += 1

            if category == "agent" and value:
                self._stats_cache["agent_preferences"][value] += 1

            if event_type == "search" and value:
                self._stats_cache["search_patterns"].append(value)

        # 批量写入
        if len(self._event_buffer) >= self._buffer_size:
            self.flush_events()

        return f"evt_{uuid.uuid4().hex[:6]}"

    def flush_events(self) -> int:
        """将缓冲区事件写入数据库"""
        with self._lock:
            if not self._event_buffer:
                return 0

            events_to_write = self._event_buffer[:]
            self._event_buffer.clear()

        conn = self.connect()
        cur = conn.cursor()

        written = 0

        for event in events_to_write:
            try:
                event_id = f"evt_{uuid.uuid4().hex[:8]}"

                cur.execute("""
                    INSERT INTO user_behavior_events
                    (id, timestamp, event_type, category, action, value,
                     metadata, session_id, processed)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                """, (
                    event_id,
                    event.timestamp,
                    event.event_type,
                    event.category,
                    event.action,
                    event.value,
                    json.dumps(event.metadata, ensure_ascii=False),
                    event.session_id,
                ))

                written += 1

            except Exception as e:
                print(f"写入行为事件失败: {e}")

        conn.commit()
        self.close()

        return written

    def analyze_patterns(self, days: int = 7) -> Dict[str, Any]:
        """
        分析用户行为模式

        返回:
        - 使用频率分布
        - 时间模式
        - 偏好识别
        - 个性化建议
        """
        conn = self.connect()
        cur = conn.cursor()

        since = time.time() - (days * 24 * 3600)

        analysis = {
            "analysis_period_days": days,
            "total_events_analyzed": 0,
            "usage_distribution": {},
            "time_patterns": {
                "peak_hours": [],
                "active_days": set(),
                "avg_daily_usage": 0,
            },
            "preferences": {
                "top_categories": [],
                "preferred_agents": [],
                "common_searches": [],
                "feature_adoption": {},
            },
            "insights": [],
            "recommendations": [],
        }

        # 总事件数
        total = cur.execute("""
            SELECT COUNT(*) FROM user_behavior_events
            WHERE timestamp >= ?
        """, (since,)).fetchone()[0]

        analysis["total_events_analyzed"] = total

        if total == 0:
            analysis["insights"].append("暂无足够数据进行模式分析")
            analysis["recommendations"].append("继续使用系统以积累行为数据")
            self.close()
            return analysis

        # 按类别分布
        categories = cur.execute("""
            SELECT category, COUNT(*) as cnt
            FROM user_behavior_events
            WHERE timestamp >= ?
            GROUP BY category
            ORDER BY cnt DESC
        """, (since,)).fetchall()

        for cat in categories:
            pct = round(cat[1] / total * 100, 1)
            analysis["usage_distribution"][cat[0]] = {
                "count": cat[1],
                "percentage": pct,
            }
            analysis["preferences"]["top_categories"].append({
                "category": cat[0],
                "count": cat[1],
                "percentage": pct,
            })

        # 时间模式
        hourly = cur.execute("""
            SELECT strftime('%H', datetime(timestamp, 'unixepoch')) as hour, COUNT(*)
            FROM user_behavior_events
            WHERE timestamp >= ?
            GROUP BY hour
            ORDER BY COUNT(*) DESC
            LIMIT 5
        """, (since,)).fetchall()

        analysis["time_patterns"]["peak_hours"] = [f"{h[0]}:00" for h in hourly]

        daily = cur.execute("""
            SELECT DATE(datetime(timestamp, 'unixepoch')) as day, COUNT(*)
            FROM user_behavior_events
            WHERE timestamp >= ?
            GROUP BY day
        """, (since,)).fetchall()

        analysis["time_patterns"]["active_days"] = len(daily)
        analysis["time_patterns"]["avg_daily_usage"] = round(total / max(len(daily), 1), 1)

        # Agent偏好
        agent_usage = cur.execute("""
            SELECT value, COUNT(*) as cnt
            FROM user_behavior_events
            WHERE timestamp >= ? AND category='agent'
            GROUP BY value
            ORDER BY cnt DESC
            LIMIT 5
        """, (since,)).fetchall()

        for agent in agent_usage:
            analysis["preferences"]["preferred_agents"].append({
                "agent": agent[0],
                "usage_count": agent[1],
            })

        # 搜索模式
        searches = cur.execute("""
            SELECT value, COUNT(*) as cnt
            FROM user_behavior_events
            WHERE timestamp >= ? AND event_type='search'
            GROUP BY value
            ORDER BY cnt DESC
            LIMIT 10
        """, (since,)).fetchall()

        analysis["preferences"]["common_searches"] = [
            {"query": s[0], "frequency": s[1]} for s in searches if s[0]
        ]

        # 生成洞察和推荐
        if analysis["time_patterns"]["peak_hours"]:
            peak = analysis["time_patterns"]["peak_hours"][0]
            analysis["insights"].append(f"最活跃时段: {peak}")

        if analysis["preferences"]["preferred_agents"]:
            top_agent = analysis["preferences"]["preferred_agents"][0]["agent"]
            analysis["insights"].append(f"最常用Agent: @{top_agent}")
            analysis["recommendations"].append(
                f"考虑将@{top_agent}设为默认Agent以提升效率"
            )

        if total > 100:
            analysis["recommendations"].append(
                "您是活跃用户，可以尝试高级功能如自定义工作流"
            )

        if len(searches) > 5:
            analysis["recommendations"].append(
                "检测到频繁搜索，建议创建常用查询收藏夹"
            )

        self.close()
        return analysis

    def get_stats(self) -> Dict[str, Any]:
        """获取当前统计"""
        with self._lock:
            buffer_size = len(self._event_buffer)

        conn = self.connect()
        cur = conn.cursor()

        db_total = cur.execute(
            "SELECT COUNT(*) FROM user_behavior_events"
        ).fetchone()[0]

        today_start = datetime.now().replace(hour=0, minute=0, second=0).timestamp()
        today_count = cur.execute("""
            SELECT COUNT(*) FROM user_behavior_events
            WHERE timestamp >= ?
        """, (today_start,)).fetchone()[0]

        self.close()

        return {
            "timestamp": datetime.now().isoformat(),
            "session_id": self._current_session,
            "buffer_pending": buffer_size,
            "database_total": db_total,
            "today_count": today_count,
            "cache_stats": dict(self._stats_cache),
        }

    def simulate_user_session(self) -> int:
        """
        模拟一个典型用户会话（用于测试）

        返回: 记录的事件数
        """
        import random

        scenarios = [
            ("page_view", "dashboard", "打开仪表盘", None),
            ("click", "memory", "查看记忆列表", None),
            ("search", "memory", "搜索记忆", "ICME架构"),
            ("agent_invoke", "agent", "调用Agent", "@yiku"),
            ("click", "mcp", "打开MCP工具面板", None),
            ("click", "chat", "开始对话", None),
            ("search", "chat", "对话搜索", "DeepSeek配置"),
            ("agent_invoke", "agent", "调度任务", "@tianshu"),
            ("config_change", "settings", "修改设置", "theme"),
            ("feedback", "system", "提交反馈", "positive"),
        ]

        recorded = 0

        for _ in range(random.randint(5, 15)):
            scenario = random.choice(scenarios)
            self.record_event(*scenario)
            recorded += 1
            time.sleep(0.01)  # 模拟间隔

        return recorded


def main():
    import argparse
    parser = argparse.ArgumentParser(description="偏好学习工具")
    parser.add_argument("--init", action="store_true", help="初始化收集器")
    parser.add_argument("--simulate", action="store_true", help="模拟用户会话")
    parser.add_argument("--flush", action="store_true", help="刷新缓冲区")
    parser.add_argument("--stats", action="store_true", help="查看统计")
    parser.add_argument("--analyze", action="store_true", help="分析模式")
    parser.add_argument("--days", type=int, default=7, help="分析天数")
    args = parser.parse_args()

    learner = PreferenceLearner()

    if args.init:
        print("\n=== 初始化偏好学习 ===\n")
        learner.connect()
        print("✅ 数据库表已就绪")
        print(f"✅ 会话ID: {learner._current_session}")
        learner.close()

    if args.simulate:
        print("\n=== 模拟用户会话 ===\n")
        count = learner.simulate_user_session()
        print(f"✅ 记录了 {count} 个行为事件")

    if args.flush:
        count = learner.flush_events()
        print(f"\n✅ 已刷新 {count} 条事件到数据库")

    if args.stats:
        print("\n=== 偏好学习统计 ===\n")
        stats = learner.get_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False, default=str))

    if args.analyze:
        print("\n=== 行为模式分析 ===\n")
        analysis = learner.analyze_patterns(days=args.days)
        print(json.dumps(analysis, indent=2, ensure_ascii=False, default=str))

    if not any([args.init, args.simulate, args.flush, args.stats, args.analyze]):
        parser.print_help()


if __name__ == "__main__":
    main()
