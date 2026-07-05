"""
锦书 — L3 成品导出Agent
==========================
格式导出、成品美化、模板应用、输出验证。

灵境道谱溯源: D7-2【格式断裂煞】· 道七·创作体道
位置: agents/jinshu.py
MCP归属: command-executor
绑定工具: execute_command, memory_recall, tianji_export
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.memory.amim import AgentMCPIntegrationManager, AgentDefinition


class JinshuAgent:

    AGENT_ID = "jinshu"

    EXPORT_FORMATS = ["json", "markdown", "text", "html", "yaml", "csv"]

    TEMPLATES = {
        "report": {
            "header": "# {title}\n\n生成时间: {timestamp}\n\n---\n",
            "body": "## {section}\n\n{content}\n\n",
            "footer": "\n---\n*由锦书导出引擎生成*",
        },
        "code": {
            "header": "```{language}\n",
            "body": "{content}",
            "footer": "\n```",
        },
    }

    def __init__(self, amim: AgentMCPIntegrationManager):
        self.amim = amim
        self.defn: AgentDefinition = amim.get_agent(self.AGENT_ID)
        self._export_log: List[Dict[str, Any]] = []

    @property
    def emoji(self) -> str:
        return self.defn.emoji

    @property
    def name(self) -> str:
        return self.defn.name

    def handle(self, task) -> Dict[str, Any]:
        action = getattr(task, "action", "export")
        payload = getattr(task, "payload", {})
        print(f"[TVP] {self.emoji} {self.name}(L3) 导出: {action}")

        handlers = {
            "export": self.export_format,
            "beautify": self.beautify_output,
            "template": self.apply_template,
            "validate": self.validate_output,
        }
        handler = handlers.get(action, self.export_format)
        return handler(payload)

    def export_format(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        content = payload.get("content", "")
        fmt = payload.get("format", "markdown")
        title = payload.get("title", "export")

        if fmt not in self.EXPORT_FORMATS:
            return {"status": "unsupported_format", "format": fmt, "supported": self.EXPORT_FORMATS}

        exporters = {
            "json": lambda c: json.dumps({"content": c, "title": title}, ensure_ascii=False, indent=2),
            "markdown": lambda c: f"# {title}\n\n{c}",
            "text": lambda c: c,
            "html": lambda c: f"<html><body><h1>{title}</h1><pre>{c}</pre></body></html>",
            "yaml": lambda c: f"title: {title}\ncontent: |\n  " + c.replace("\n", "\n  "),
            "csv": lambda c: "title,content\n" + f"{title},\"{c}\"",
        }

        exported = exporters.get(fmt, lambda c: c)(content)
        export_entry = {
            "format": fmt,
            "title": title,
            "size": len(exported),
            "timestamp": time.time(),
        }
        self._export_log.append(export_entry)

        print(f"[TVP] {self.emoji} 锦书: 导出 [{fmt}] {len(exported)} 字符")
        return {"status": "exported", "format": fmt, "size": len(exported), "output": exported}

    def beautify_output(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        content = payload.get("content", "")
        style = payload.get("style", "clean")

        if style == "clean":
            beautified = content.replace("\r\n", "\n").strip()
        elif style == "prettify":
            beautified = content.strip()
            beautified = "\n\n".join(line.strip() for line in beautified.split("\n") if line.strip())
        else:
            beautified = content

        return {"status": "beautified", "style": style, "original_size": len(content), "final_size": len(beautified), "output": beautified}

    def apply_template(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        template_name = payload.get("template", "report")
        template = self.TEMPLATES.get(template_name, self.TEMPLATES["report"])
        content = payload.get("content", "")
        title = payload.get("title", "文档")
        section = payload.get("section", "正文")

        output = (
            template["header"].format(title=title, timestamp=time.strftime("%Y-%m-%d %H:%M:%S")) +
            template["body"].format(section=section, content=content) +
            template["footer"]
        )
        return {"status": "templated", "template": template_name, "output": output}

    def validate_output(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        output = payload.get("output", "")
        fmt = payload.get("format", "markdown")
        checks = {
            "not_empty": bool(output),
            "valid_json": self._is_valid_json(output) if fmt == "json" else True,
            "reasonable_size": len(output) < 10 * 1024 * 1024,
        }
        all_valid = all(checks.values())
        return {"status": "valid" if all_valid else "invalid", "checks": checks}

    def _is_valid_json(self, text: str) -> bool:
        try:
            json.loads(text)
            return True
        except (json.JSONDecodeError, ValueError):
            return False

    def health(self) -> Dict[str, Any]:
        return {
            "agent_id": self.AGENT_ID,
            "name": self.name,
            "layer": f"L{self.defn.layer.value}",
            "status": "healthy",
            "exports_count": len(self._export_log),
            "formats": self.EXPORT_FORMATS,
            "templates": list(self.TEMPLATES.keys()),
            "tools": self.defn.tools,
            "mcp_server": self.defn.mcp_server,
        }
