r"""
TDAF Adapters - 天机跨平台适配层 v1.0
=======================================
D19: TDAF适配到不同AI平台的上下文格式
TraeAdapter / CursorAdapter / CopilotAdapter / MarkdownAdapter
"""

import json
import time
from typing import Optional, List, Dict
from pathlib import Path


class BaseAdapter:
    PLATFORM = "base"

    def adapt(self, tdaf_data: dict) -> str:
        raise NotImplementedError

    def adapt_to_files(self, tdaf_data: dict, output_dir: str) -> List[str]:
        content = self.adapt(tdaf_data)
        output_path = Path(output_dir) / self._get_filename()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        return [str(output_path)]

    def _get_filename(self) -> str:
        return f"tianji_export.{self.PLATFORM}"


class TraeAdapter(BaseAdapter):
    PLATFORM = "trae"

    def adapt(self, tdaf_data: dict) -> str:
        lines = []
        lines.append("# Tianji Digital Asset Export — Trae Format")
        lines.append("")
        lines.append("## Asset Manifest")
        manifest = tdaf_data.get("asset_manifest", {})
        lines.append(f"- Total Assets: {manifest.get('total_assets', 0)}")
        for layer, count in manifest.get("by_layer", {}).items():
            lines.append(f"- {layer}: {count}")
        lines.append("")

        assets = tdaf_data.get("assets", [])
        if assets:
            lines.append("## Assets")
            lines.append("")
            for asset in assets:
                asset_id = asset.get("asset_id", "")
                layer = asset.get("layer", "")
                ct = asset.get("content_type", "")
                status = asset.get("status", "")
                tags = asset.get("tags", [])
                content = asset.get("content", "")

                lines.append(f"### {asset_id}")
                lines.append(f"- Layer: {layer}")
                lines.append(f"- Type: {ct}")
                lines.append(f"- Status: {status}")
                if tags:
                    lines.append(f"- Tags: {', '.join(tags)}")
                if content:
                    lines.append("")
                    lines.append("```")
                    lines.append(content[:2000])
                    if len(content) > 2000:
                        lines.append("... (truncated)")
                    lines.append("```")
                lines.append("")

        kg = tdaf_data.get("knowledge_graph", {})
        nodes = kg.get("nodes", [])
        edges = kg.get("edges", [])
        if nodes or edges:
            lines.append("## Knowledge Graph")
            lines.append("")
            lines.append(f"Nodes: {len(nodes)}, Edges: {len(edges)}")
            for edge in edges[:50]:
                lines.append(f"- {edge.get('source', '')} --[{edge.get('predicate', '')}]--> {edge.get('target', '')}")
            lines.append("")

        return "\n".join(lines)

    def _get_filename(self) -> str:
        return "tianji_export.md"


class CursorAdapter(BaseAdapter):
    PLATFORM = "cursor"

    def adapt(self, tdaf_data: dict) -> str:
        lines = []
        lines.append("---")
        lines.append("tianji_export: true")
        lines.append(f"export_timestamp: {tdaf_data.get('export_timestamp', 0)}")
        manifest = tdaf_data.get("asset_manifest", {})
        lines.append(f"total_assets: {manifest.get('total_assets', 0)}")
        lines.append("---")
        lines.append("")

        assets = tdaf_data.get("assets", [])
        for asset in assets:
            layer = asset.get("layer", "")
            content = asset.get("content", "")
            tags = asset.get("tags", [])
            if content:
                lines.append(f"## [{layer.upper()}] {asset.get('asset_id', '')}")
                if tags:
                    lines.append(f"Tags: {', '.join(tags)}")
                lines.append("")
                lines.append(content[:3000])
                lines.append("")

        kg = tdaf_data.get("knowledge_graph", {})
        edges = kg.get("edges", [])
        if edges:
            lines.append("## Knowledge Triples")
            lines.append("")
            for edge in edges[:100]:
                lines.append(f"- {edge.get('source', '')} | {edge.get('predicate', '')} | {edge.get('target', '')}")
            lines.append("")

        return "\n".join(lines)

    def _get_filename(self) -> str:
        return ".cursorrules"


class CopilotAdapter(BaseAdapter):
    PLATFORM = "copilot"

    def adapt(self, tdaf_data: dict) -> str:
        lines = []
        lines.append("# Tianji Memory Context for GitHub Copilot")
        lines.append("")

        assets = tdaf_data.get("assets", [])
        semantic_assets = [a for a in assets if a.get("layer") == "semantic"]
        episodic_assets = [a for a in assets if a.get("layer") == "episodic"]

        if semantic_assets:
            lines.append("## Knowledge Base")
            lines.append("")
            for asset in semantic_assets[:50]:
                content = asset.get("content", "")
                tags = asset.get("tags", [])
                if content:
                    lines.append(f"### {', '.join(tags) if tags else asset.get('asset_id', '')}")
                    lines.append(content[:1000])
                    lines.append("")

        if episodic_assets:
            lines.append("## Recent Events")
            lines.append("")
            for asset in episodic_assets[:20]:
                content = asset.get("content", "")
                if content:
                    lines.append(f"- {content[:200]}")

        return "\n".join(lines)

    def adapt_to_files(self, tdaf_data: dict, output_dir: str) -> List[str]:
        content = self.adapt(tdaf_data)
        github_dir = Path(output_dir) / ".github"
        github_dir.mkdir(parents=True, exist_ok=True)
        copilot_path = github_dir / "copilot-instructions.md"
        with open(copilot_path, "w", encoding="utf-8") as f:
            f.write(content)
        return [str(copilot_path)]


class MarkdownAdapter(BaseAdapter):
    PLATFORM = "markdown"

    def adapt(self, tdaf_data: dict) -> str:
        lines = []
        lines.append("# Tianji Digital Asset Export")
        lines.append("")
        manifest = tdaf_data.get("asset_manifest", {})
        lines.append(f"**Export Time**: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(tdaf_data.get('export_timestamp', 0)))}")
        lines.append(f"**Total Assets**: {manifest.get('total_assets', 0)}")
        lines.append("")

        by_layer = manifest.get("by_layer", {})
        if by_layer:
            lines.append("| Layer | Count |")
            lines.append("|-------|-------|")
            for layer, count in sorted(by_layer.items()):
                lines.append(f"| {layer} | {count} |")
            lines.append("")

        assets = tdaf_data.get("assets", [])
        for asset in assets:
            asset_id = asset.get("asset_id", "")
            layer = asset.get("layer", "")
            content = asset.get("content", "")
            tags = asset.get("tags", [])
            triples = asset.get("triples", [])

            lines.append(f"## {asset_id}")
            lines.append(f"- Layer: {layer}")
            lines.append(f"- Type: {asset.get('content_type', '')}")
            if tags:
                lines.append(f"- Tags: {', '.join(tags)}")
            lines.append("")

            if content:
                lines.append(content[:5000])
                lines.append("")

            if triples:
                lines.append("### Knowledge Triples")
                for t in triples[:20]:
                    lines.append(f"- {t.get('subject', '')} → {t.get('predicate', '')} → {t.get('object', '')}")
                lines.append("")

        kg = tdaf_data.get("knowledge_graph", {})
        edges = kg.get("edges", [])
        if edges:
            lines.append("---")
            lines.append("## Knowledge Graph")
            lines.append("")
            for edge in edges[:200]:
                lines.append(f"- **{edge.get('source', '')}** --[{edge.get('predicate', '')}]--> **{edge.get('target', '')}**")
            lines.append("")

        return "\n".join(lines)

    def _get_filename(self) -> str:
        return "tianji_knowledge_base.md"


ADAPTER_MAP = {
    "trae": TraeAdapter,
    "cursor": CursorAdapter,
    "copilot": CopilotAdapter,
    "markdown": MarkdownAdapter,
}


def adapt(tdaf_data: dict, platform: str) -> str:
    adapter_cls = ADAPTER_MAP.get(platform)
    if not adapter_cls:
        raise ValueError(f"Unknown platform: {platform}. Available: {list(ADAPTER_MAP.keys())}")
    adapter = adapter_cls()
    return adapter.adapt(tdaf_data)


def adapt_to_files(tdaf_data: dict, platform: str, output_dir: str) -> List[str]:
    adapter_cls = ADAPTER_MAP.get(platform)
    if not adapter_cls:
        raise ValueError(f"Unknown platform: {platform}. Available: {list(ADAPTER_MAP.keys())}")
    adapter = adapter_cls()
    return adapter.adapt_to_files(tdaf_data, output_dir)
