r"""
天机对话内容提取引擎 v2.0 — 多平台支持
===========================================
从 Trae History / Qoder Cache 目录提取完整对话内容，
支持按日期范围过滤、去重、分批输出。

数据源:
  Trae:  C:\Users\Administrator\AppData\Roaming\Trae CN\User\History\
  Qoder: C:\Users\Administrator\.qoder\cache\projects\

Trae会话目录结构:
  - entries.json: 会话元数据+条目列表
  - *.py / *.json / *.md 等文件: 对话内容文件

Qoder会话目录结构:
  - {conversation_id}.jsonl: JSONL格式对话记录 (每行: {"role":"user"/"assistant","message":"..."})
"""

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from core.shared.platform_detector import (
    PLATFORM_QODER,
    PLATFORM_TRAE,
    PLATFORM_UNKNOWN,
    get_history_path_for_platform,
    get_platform,
)


@dataclass
class TraeConversation:
    id: str
    path: str
    time: str
    timestamp: float
    resource: str
    entry_count: int
    file_count: int
    total_file_size: int
    files: list[dict] = field(default_factory=list)
    content_text: str = ""
    content_sources: list[str] = field(default_factory=list)
    content_hash: str = ""
    extracted: bool = False
    error: str | None = None
    platform: str = PLATFORM_UNKNOWN  # v2.0: 平台标记 (qoder/trae/cursor/cline/unknown)


class TraeContentExtractor:
    def __init__(self, history_path: str | None = None, output_path: str = ""):
        if history_path:
            self._history_path = Path(history_path)
        else:
            self._history_path = get_history_path_for_platform() or Path(".")
        self._output_path = Path(output_path) if output_path else Path("data/extracted")
        self._output_path.mkdir(parents=True, exist_ok=True)
        self._conversations: list[TraeConversation] = []
        self._content_index: dict[str, str] = {}
        self._dedup_set: set = set()
        self._platform = get_platform()  # v2.0: 自动检测平台

    def scan_conversations(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[TraeConversation]:
        self._conversations = []

        if not self._history_path.exists():
            print(f"History path not found: {self._history_path}")
            return []

        # v2.0: 根据平台选择不同的扫描策略
        if self._platform == PLATFORM_QODER:
            return self._scan_qoder_conversations(start_date, end_date)
        else:
            return self._scan_trae_conversations(start_date, end_date)

    def _scan_qoder_conversations(
        self, start_date: datetime, end_date: datetime
    ) -> list[TraeConversation]:
        """扫描 Qoder 对话历史 (JSONL格式)"""
        for project_dir in sorted(self._history_path.iterdir()):
            if not project_dir.is_dir():
                continue
            conv_history_dir = project_dir / "conversation-history"
            if not conv_history_dir.exists():
                continue

            for conv_dir in sorted(conv_history_dir.iterdir()):
                if not conv_dir.is_dir():
                    continue
                # Qoder: 每个对话目录下有一个同名的 .jsonl 文件
                jsonl_file = conv_dir / f"{conv_dir.name}.jsonl"
                if not jsonl_file.exists():
                    # 也尝试查找其他 .jsonl 文件
                    jsonl_files = list(conv_dir.glob("*.jsonl"))
                    if jsonl_files:
                        jsonl_file = jsonl_files[0]
                    else:
                        continue

                try:
                    mtime = datetime.fromtimestamp(jsonl_file.stat().st_mtime)
                    ctime = datetime.fromtimestamp(os.path.getctime(str(jsonl_file)))
                    conv_time = min(mtime, ctime) if ctime < mtime else mtime

                    if not (start_date <= conv_time <= end_date):
                        continue

                    # 读取JSONL获取条目数
                    entry_count = 0
                    try:
                        with open(
                            str(jsonl_file), encoding="utf-8-sig", errors="replace"
                        ) as f:
                            for line in f:
                                line = line.strip()
                                if line:
                                    entry_count += 1
                    except Exception:
                        pass

                    conv = TraeConversation(
                        id=conv_dir.name,
                        path=str(conv_dir),
                        time=conv_time.strftime("%Y-%m-%d %H:%M:%S"),
                        timestamp=conv_time.timestamp(),
                        resource="qoder",
                        entry_count=entry_count,
                        file_count=1,
                        total_file_size=jsonl_file.stat().st_size,
                        files=[
                            {
                                "name": jsonl_file.name,
                                "size": jsonl_file.stat().st_size,
                                "suffix": ".jsonl",
                                "path": str(jsonl_file),
                            }
                        ],
                        platform=PLATFORM_QODER,
                    )
                    self._conversations.append(conv)

                except Exception as e:
                    self._conversations.append(
                        TraeConversation(
                            id=conv_dir.name,
                            path=str(conv_dir),
                            time="",
                            timestamp=0,
                            resource="error",
                            entry_count=0,
                            file_count=0,
                            total_file_size=0,
                            error=str(e),
                            platform=PLATFORM_QODER,
                        )
                    )

        self._conversations.sort(key=lambda x: x.timestamp)
        print(f"Scanned {len(self._conversations)} Qoder conversations in date range")
        return self._conversations

    def _scan_trae_conversations(
        self, start_date: datetime, end_date: datetime
    ) -> list[TraeConversation]:
        """扫描 Trae 对话历史 (entries.json格式)"""
        for item in sorted(self._history_path.iterdir()):
            if not item.is_dir():
                continue
            entries_file = item / "entries.json"
            if not entries_file.exists():
                continue

            try:
                mtime = datetime.fromtimestamp(entries_file.stat().st_mtime)
                ctime = datetime.fromtimestamp(os.path.getctime(str(entries_file)))
                conv_time = min(mtime, ctime) if ctime < mtime else mtime

                if not (start_date <= conv_time <= end_date):
                    continue

                with open(
                    str(entries_file), encoding="utf-8-sig", errors="replace"
                ) as f:
                    raw = json.load(f)

                entries = raw.get("entries", [])
                resource = raw.get("resource", "unknown")

                files_in_dir = []
                total_file_size = 0
                for f in item.iterdir():
                    if f.name != "entries.json":
                        files_in_dir.append(
                            {
                                "name": f.name,
                                "size": f.stat().st_size,
                                "suffix": f.suffix,
                                "path": str(f),
                            }
                        )
                        total_file_size += f.stat().st_size

                conv = TraeConversation(
                    id=item.name,
                    path=str(item),
                    time=conv_time.strftime("%Y-%m-%d %H:%M:%S"),
                    timestamp=conv_time.timestamp(),
                    resource=resource,
                    entry_count=len(entries) if isinstance(entries, list) else 1,
                    file_count=len(files_in_dir),
                    total_file_size=total_file_size,
                    files=files_in_dir,
                    platform=PLATFORM_TRAE,
                )

                self._conversations.append(conv)

            except Exception as e:
                self._conversations.append(
                    TraeConversation(
                        id=item.name,
                        path=str(item),
                        time="",
                        timestamp=0,
                        resource="error",
                        entry_count=0,
                        file_count=0,
                        total_file_size=0,
                        error=str(e),
                        platform=PLATFORM_TRAE,
                    )
                )

        self._conversations.sort(key=lambda x: x.timestamp)
        print(f"Scanned {len(self._conversations)} Trae conversations in date range")
        return self._conversations

    def extract_content(self, conv: TraeConversation) -> TraeConversation:
        if conv.error:
            return conv

        # v2.0: 根据平台选择不同的提取策略
        if conv.platform == PLATFORM_QODER:
            return self._extract_qoder_content(conv)
        else:
            return self._extract_trae_content(conv)

    def _extract_qoder_content(self, conv: TraeConversation) -> TraeConversation:
        """提取 Qoder JSONL 格式对话内容"""
        content_parts = []
        sources = []
        conv_dir = Path(conv.path)

        jsonl_file = conv_dir / f"{conv.id}.jsonl"
        if not jsonl_file.exists():
            jsonl_files = list(conv_dir.glob("*.jsonl"))
            if jsonl_files:
                jsonl_file = jsonl_files[0]
            else:
                conv.error = "No JSONL file found"
                return conv

        try:
            with open(str(jsonl_file), encoding="utf-8-sig", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    role = entry.get("role", "unknown")
                    msg = entry.get("message", "")
                    if isinstance(msg, str):
                        text = msg
                    elif isinstance(msg, dict):
                        content_list = msg.get("content", [])
                        if isinstance(content_list, list):
                            text_parts = []
                            for item in content_list:
                                if (
                                    isinstance(item, dict)
                                    and item.get("type") == "text"
                                ):
                                    text_parts.append(item.get("text", ""))
                            text = "\n".join(text_parts)
                        else:
                            text = str(msg)
                    else:
                        text = str(msg)

                    if text.strip():
                        prefix = (
                            "[User]"
                            if role == "user"
                            else "[Assistant]"
                            if role == "assistant"
                            else f"[{role}]"
                        )
                        content_parts.append(f"{prefix} {text[:3000]}")
                        sources.append("jsonl")
        except Exception as e:
            content_parts.append(f"[JSONL读取错误: {e}]")

        conv.content_text = "\n".join(content_parts)
        conv.content_sources = sources
        conv.content_hash = hashlib.sha256(conv.content_text.encode()).hexdigest()[:16]
        conv.extracted = True
        return conv

    def _extract_trae_content(self, conv: TraeConversation) -> TraeConversation:
        """提取 Trae entries.json 格式对话内容"""
        content_parts = []
        sources = []
        conv_dir = Path(conv.path)

        entries_file = conv_dir / "entries.json"
        if entries_file.exists():
            try:
                with open(
                    str(entries_file), encoding="utf-8-sig", errors="replace"
                ) as f:
                    raw = json.load(f)
                entries = raw.get("entries", [])
                if isinstance(entries, list):
                    for entry in entries:
                        if isinstance(entry, dict):
                            text = entry.get("content", entry.get("text", ""))
                            if text:
                                content_parts.append(str(text)[:2000])
                                sources.append("entries.json")
                        elif isinstance(entry, str):
                            content_parts.append(entry[:2000])
                            sources.append("entries.json")
            except Exception as e:
                content_parts.append(f"[entries.json读取错误: {e}]")

        for file_info in conv.files:
            fp = conv_dir / file_info["name"]
            if not fp.exists():
                continue
            suffix = file_info.get("suffix", "")
            try:
                if suffix in (
                    ".py",
                    ".js",
                    ".ts",
                    ".tsx",
                    ".bat",
                    ".ps1",
                    ".sh",
                    ".json",
                    ".md",
                    ".txt",
                    ".yml",
                    ".yaml",
                    ".conf",
                    ".cfg",
                    ".sql",
                    ".html",
                    ".css",
                    ".svg",
                    ".vbs",
                    ".spec",
                    ".iss",
                    ".template",
                    ".example",
                    ".local",
                    ".dev",
                    ".development",
                    ".production",
                    "._pth",
                    ".cs",
                    "",
                ):
                    text = fp.read_text(encoding="utf-8-sig", errors="replace")
                    if text.strip():
                        content_parts.append(
                            f"\n--- 文件: {file_info['name']} ---\n{text[:3000]}"
                        )
                        sources.append(file_info["name"])
            except Exception:
                pass

        conv.content_text = "\n".join(content_parts)
        conv.content_sources = sources
        conv.content_hash = hashlib.sha256(conv.content_text.encode()).hexdigest()[:16]
        conv.extracted = True

        return conv

    def extract_all(self) -> list[TraeConversation]:
        for i, conv in enumerate(self._conversations):
            if conv.error:
                continue
            self.extract_content(conv)
            if (i + 1) % 100 == 0:
                print(f"  Extracted {i + 1}/{len(self._conversations)}")
        return self._conversations

    def build_dedup_index(self) -> dict:
        self._dedup_set = set()
        dedup_stats = {"total": 0, "unique": 0, "duplicates": 0}
        for conv in self._conversations:
            if not conv.extracted or not conv.content_hash:
                continue
            dedup_stats["total"] += 1
            if conv.content_hash in self._dedup_set:
                dedup_stats["duplicates"] += 1
            else:
                self._dedup_set.add(conv.content_hash)
                dedup_stats["unique"] += 1
        return dedup_stats

    def get_unique_conversations(self) -> list[TraeConversation]:
        seen = set()
        unique = []
        for conv in self._conversations:
            if not conv.extracted or conv.error:
                continue
            if conv.content_hash not in seen:
                seen.add(conv.content_hash)
                unique.append(conv)
        return unique

    def create_batches(self, batch_size: int = 20) -> list[list[TraeConversation]]:
        unique = self.get_unique_conversations()
        batches = []
        for i in range(0, len(unique), batch_size):
            batches.append(unique[i : i + batch_size])
        return batches

    def save_batch_report(self, batch_index: int, batch: list[TraeConversation]) -> str:
        report_file = self._output_path / f"batch_{batch_index:04d}_report.json"
        report = {
            "batch_index": batch_index,
            "batch_size": len(batch),
            "conversations": [],
        }
        for conv in batch:
            report["conversations"].append(
                {
                    "id": conv.id,
                    "time": conv.time,
                    "resource": conv.resource,
                    "entry_count": conv.entry_count,
                    "file_count": conv.file_count,
                    "total_file_size": conv.total_file_size,
                    "content_hash": conv.content_hash,
                    "content_length": len(conv.content_text),
                    "content_sources": conv.content_sources,
                    "content_preview": conv.content_text[:500],
                }
            )
        with open(str(report_file), "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        return str(report_file)

    def save_full_extraction(self) -> str:
        output_file = self._output_path / "full_extraction.json"
        data = {
            "extraction_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_conversations": len(self._conversations),
            "extracted_count": len([c for c in self._conversations if c.extracted]),
            "error_count": len([c for c in self._conversations if c.error]),
            "conversations": [],
        }
        for conv in self._conversations:
            if not conv.extracted:
                continue
            data["conversations"].append(
                {
                    "id": conv.id,
                    "time": conv.time,
                    "timestamp": conv.timestamp,
                    "resource": conv.resource,
                    "entry_count": conv.entry_count,
                    "file_count": conv.file_count,
                    "total_file_size": conv.total_file_size,
                    "content_hash": conv.content_hash,
                    "content_text": conv.content_text[:5000],
                    "content_sources": conv.content_sources,
                }
            )
        with open(str(output_file), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        return str(output_file)

    def save_gap_analysis(self, tianji_memories: list[dict]) -> str:
        tianji_timestamps = set()
        tianji_hashes = set()
        for mem in tianji_memories:
            ts = mem.get("timestamp", 0)
            if ts:
                date_key = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                tianji_timestamps.add(date_key)
            h = mem.get("content_hash", "")
            if h:
                tianji_hashes.add(h)

        trae_dates = {}
        for conv in self._conversations:
            if not conv.extracted or conv.error:
                continue
            date_key = conv.time[:10] if conv.time else "unknown"
            if date_key not in trae_dates:
                trae_dates[date_key] = {"trae_count": 0, "conversations": []}
            trae_dates[date_key]["trae_count"] += 1
            trae_dates[date_key]["conversations"].append(conv.id)

        gap_list = []
        for date_key in sorted(trae_dates.keys()):
            trae_count = trae_dates[date_key]["trae_count"]
            in_tianji = date_key in tianji_timestamps
            status = "PRESENT" if in_tianji else "MISSING"
            gap_list.append(
                {
                    "date": date_key,
                    "trae_conversations": trae_count,
                    "in_tianji": in_tianji,
                    "status": status,
                    "conversation_ids": trae_dates[date_key]["conversations"],
                }
            )

        report = {
            "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "trae_total": len([c for c in self._conversations if c.extracted]),
            "tianji_total": len(tianji_memories),
            "total_gap": len([g for g in gap_list if g["status"] == "MISSING"]),
            "gap_details": gap_list,
        }

        output_file = self._output_path / "gap_analysis.json"
        with open(str(output_file), "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        return str(output_file)

    def get_stats(self) -> dict:
        extracted = [c for c in self._conversations if c.extracted]
        errors = [c for c in self._conversations if c.error]
        total_content_size = sum(len(c.content_text) for c in extracted)
        return {
            "total": len(self._conversations),
            "extracted": len(extracted),
            "errors": len(errors),
            "total_content_size": total_content_size,
            "avg_content_size": total_content_size // max(len(extracted), 1),
            "date_range": {
                "earliest": self._conversations[0].time
                if self._conversations
                else None,
                "latest": self._conversations[-1].time if self._conversations else None,
            },
        }
