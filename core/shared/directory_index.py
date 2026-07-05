r"""
DirectorySmartIndex - 天机目录智能索引 v1.0
=============================================
D13: DirectorySmartIndex数据模型+扫描器
D14: README智能索引生成器
"""

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

LANG_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript React",
    ".jsx": "JavaScript React",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".cpp": "C++",
    ".c": "C",
    ".h": "C/C++ Header",
    ".hpp": "C++ Header",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".scala": "Scala",
    ".r": "R",
    ".R": "R",
    ".sql": "SQL",
    ".sh": "Shell",
    ".ps1": "PowerShell",
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".txt": "Text",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".xml": "XML",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".less": "Less",
    ".vue": "Vue",
    ".svelte": "Svelte",
}


@dataclass
class AIHook:
    hook_name: str = ""
    trigger: str = ""
    action: str = ""
    description: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DirChild:
    name: str = ""
    path: str = ""
    is_dir: bool = False
    content_hash: str = ""
    size_bytes: int = 0
    language: str = ""
    one_line_summary: str = ""
    asset_id: str = ""
    last_modified: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DirectorySmartIndex:
    directory_path: str = ""
    total_files: int = 0
    total_dirs: int = 0
    total_size_bytes: int = 0
    children: List[DirChild] = field(default_factory=list)
    languages: Dict[str, int] = field(default_factory=dict)
    ai_hooks: List[AIHook] = field(default_factory=list)
    ai_memory: List[str] = field(default_factory=list)
    content_hash: str = ""
    scan_timestamp: float = 0.0
    asset_id: str = ""

    def to_dict(self) -> dict:
        return {
            "directory_path": self.directory_path,
            "total_files": self.total_files,
            "total_dirs": self.total_dirs,
            "total_size_bytes": self.total_size_bytes,
            "children": [c.to_dict() for c in self.children],
            "languages": self.languages,
            "ai_hooks": [h.to_dict() for h in self.ai_hooks],
            "ai_memory": self.ai_memory,
            "content_hash": self.content_hash,
            "scan_timestamp": self.scan_timestamp,
            "asset_id": self.asset_id,
        }


class DirectoryScanner:
    SKIP_DIRS = {
        "__pycache__",
        ".git",
        ".svn",
        ".hg",
        "node_modules",
        ".venv",
        "venv",
        ".env",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        "dist",
        "build",
        ".next",
        ".nuxt",
        "target",
        "bin",
        "obj",
    }
    SKIP_EXTS = {".pyc", ".pyo", ".so", ".dll", ".exe", ".o", ".a", ".lib"}

    def __init__(self, llm_summarize_fn: Optional[Callable] = None, registry=None):
        self._llm_summarize = llm_summarize_fn
        self._registry = registry

    def scan_directory(self, dir_path: str, max_depth: int = 3) -> DirectorySmartIndex:
        path = Path(dir_path)
        if not path.exists() or not path.is_dir():
            return DirectorySmartIndex(directory_path=dir_path)

        index = DirectorySmartIndex(
            directory_path=str(path.resolve()),
            scan_timestamp=time.time(),
        )

        self._scan_recursive(path, index, depth=0, max_depth=max_depth)

        index.content_hash = self._compute_index_hash(index)
        return index

    def _scan_recursive(
        self, path: Path, index: DirectorySmartIndex, depth: int, max_depth: int
    ):
        if depth > max_depth:
            return

        try:
            entries = sorted(
                path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())
            )
        except PermissionError:
            return

        for entry in entries:
            if entry.is_dir():
                if entry.name in self.SKIP_DIRS or entry.name.startswith("."):
                    continue
                index.total_dirs += 1
                child = DirChild(
                    name=entry.name,
                    path=str(entry.resolve()),
                    is_dir=True,
                    last_modified=entry.stat().st_mtime if entry.exists() else 0.0,
                )
                index.children.append(child)
                self._scan_recursive(entry, index, depth + 1, max_depth)
            else:
                if entry.suffix in self.SKIP_EXTS:
                    continue
                try:
                    stat = entry.stat()
                except OSError:
                    continue

                content_hash = ""
                try:
                    data = entry.read_bytes()
                    content_hash = hashlib.sha256(data).hexdigest()
                except Exception:
                    pass

                lang = LANG_MAP.get(entry.suffix, "")

                summary = ""
                if self._llm_summarize:
                    try:
                        summary = self._llm_summarize(
                            str(entry), data[:2000].decode("utf-8", errors="replace")
                        )
                    except Exception:
                        pass
                elif entry.suffix == ".py":
                    summary = self._auto_summary_py(entry)

                asset_id = ""
                if self._registry and content_hash:
                    try:
                        atoms = self._registry.get_by_memory_id(str(entry.resolve()))
                        if atoms:
                            asset_id = atoms[0].asset_id
                    except Exception:
                        pass

                child = DirChild(
                    name=entry.name,
                    path=str(entry.resolve()),
                    is_dir=False,
                    content_hash=content_hash,
                    size_bytes=stat.st_size,
                    language=lang,
                    one_line_summary=summary,
                    asset_id=asset_id,
                    last_modified=stat.st_mtime,
                )
                index.children.append(child)
                index.total_files += 1
                index.total_size_bytes += stat.st_size

                if lang:
                    index.languages[lang] = index.languages.get(lang, 0) + 1

    def _auto_summary_py(self, path: Path) -> str:
        try:
            first_lines = []
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f):
                    if i >= 20:
                        break
                    stripped = line.strip()
                    if stripped.startswith('"""') or stripped.startswith("'''"):
                        if i == 0 or (i == 1 and not first_lines):
                            continue
                    if stripped.startswith("class ") or stripped.startswith("def "):
                        first_lines.append(stripped.split("(")[0])
                    if stripped.startswith('r"""') or stripped.startswith("r'''"):
                        continue
            if first_lines:
                return f"Contains: {', '.join(first_lines[:5])}"
        except Exception:
            pass
        return ""

    def _compute_index_hash(self, index: DirectorySmartIndex) -> str:
        hash_input = json.dumps(
            {
                "path": index.directory_path,
                "files": sorted([c.name for c in index.children if not c.is_dir]),
                "hashes": sorted(
                    [c.content_hash for c in index.children if c.content_hash]
                ),
            },
            sort_keys=True,
        )
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]


class READMEGenerator:
    SECTION_MARKERS = {
        "path_index": "<!-- AI-SECTION: PATH_INDEX -->",
        "file_summary": "<!-- AI-SECTION: FILE_SUMMARY -->",
        "ai_memory": "<!-- AI-SECTION: AI_MEMORY -->",
        "ai_hooks": "<!-- AI-SECTION: AI_HOOKS -->",
    }

    def generate_readme(self, dir_index: DirectorySmartIndex) -> str:
        dir_name = Path(dir_index.directory_path).name
        lines = []

        lines.append("---")
        lines.append(f"path_index: {dir_index.directory_path}")
        lines.append(f"total_files: {dir_index.total_files}")
        lines.append(f"total_dirs: {dir_index.total_dirs}")
        lines.append(f"total_size_bytes: {dir_index.total_size_bytes}")
        lines.append(f"scan_timestamp: {dir_index.scan_timestamp}")
        lines.append(f"content_hash: {dir_index.content_hash}")
        lines.append("---")
        lines.append("")

        lines.append(f"# {dir_name}")
        lines.append("")
        lines.append("Auto-generated smart index by Tianji v9.1")
        lines.append("")

        lines.append(self.SECTION_MARKERS["path_index"])
        lines.append("")
        lines.append("| Name | Type | Language | Size | Hash | Summary |")
        lines.append("|------|------|----------|------|------|---------|")
        for child in sorted(dir_index.children, key=lambda c: (not c.is_dir, c.name)):
            type_str = "DIR" if child.is_dir else "FILE"
            lang_str = child.language if child.language else "-"
            size_str = self._format_size(child.size_bytes) if not child.is_dir else "-"
            hash_str = child.content_hash[:8] if child.content_hash else "-"
            summary = child.one_line_summary[:50] if child.one_line_summary else "-"
            lines.append(
                f"| {child.name} | {type_str} | {lang_str} | {size_str} | {hash_str} | {summary} |"
            )
        lines.append("")

        lines.append(self.SECTION_MARKERS["file_summary"])
        lines.append("")
        files = [c for c in dir_index.children if not c.is_dir]
        for f in files:
            lines.append(
                f"- **{f.name}** ({f.language}): {f.one_line_summary or 'No summary'}"
            )
        lines.append("")

        lines.append(self.SECTION_MARKERS["ai_memory"])
        lines.append("")
        if dir_index.ai_memory:
            for mem in dir_index.ai_memory:
                lines.append(f"- {mem}")
        else:
            lines.append("_No cross-session memories yet._")
        lines.append("")

        lines.append(self.SECTION_MARKERS["ai_hooks"])
        lines.append("")
        if dir_index.ai_hooks:
            for hook in dir_index.ai_hooks:
                lines.append(
                    f"- **{hook.hook_name}** (trigger: `{hook.trigger}`): {hook.description}"
                )
        else:
            lines.append("<!-- AI-HOOK: on_change -->")
            lines.append("<!-- AI-HOOK: on_delete -->")
            lines.append("<!-- AI-HOOK: on_create -->")
        lines.append("")

        if dir_index.languages:
            lines.append("## Language Distribution")
            lines.append("")
            for lang, count in sorted(dir_index.languages.items(), key=lambda x: -x[1]):
                lines.append(f"- {lang}: {count} files")
            lines.append("")

        return "\n".join(lines)

    def update_readme_section(
        self, readme_content: str, section_name: str, new_content: str
    ) -> str:
        if section_name not in self.SECTION_MARKERS:
            return readme_content

        marker = self.SECTION_MARKERS[section_name]
        lines = readme_content.split("\n")
        result = []
        in_section = False
        section_start = -1

        for i, line in enumerate(lines):
            if line.strip() == marker.strip():
                in_section = True
                section_start = i
                result.append(line)
                result.append("")
                result.append(new_content)
                continue

            if in_section:
                next_markers = [
                    v for k, v in self.SECTION_MARKERS.items() if k != section_name
                ]
                if line.strip() in [m.strip() for m in next_markers]:
                    in_section = False
                    result.append("")
                    result.append(line)
                continue
            else:
                result.append(line)

        return "\n".join(result)

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f}KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f}MB"


class TianjiREADMEIntegrator:
    """天机README索引集成器 - 与天机记忆系统深度绑定"""

    def __init__(self, engine=None, registry=None):
        self._engine = engine
        self._registry = registry
        self._scanner = DirectoryScanner(registry=registry)
        self._generator = READMEGenerator()

    def scan_and_generate(
        self, dir_path: str, max_depth: int = 3, save_to_file: bool = True
    ) -> str:
        """扫描目录并生成智能README.md"""
        # 扫描目录
        index = self._scanner.scan_directory(dir_path, max_depth)

        # 注入AI记忆（从天机L3 Episodic层检索）
        if self._engine:
            try:
                memories = self._engine.recall(
                    query=f"目录:{dir_path}", layers=["episodic"], limit=5
                )
                index.ai_memory = [m.get("content", "")[:100] for m in memories]
            except Exception:
                pass

        # 生成README内容
        readme_content = self._generator.generate_readme(index)

        # 保存到文件
        if save_to_file:
            readme_path = Path(dir_path) / "README.md"
            readme_path.write_text(readme_content, encoding="utf-8")

        # 存储到天机L4 Semantic层
        if self._engine:
            try:
                self._engine.remember(
                    content=f"【目录索引】{dir_path}\n文件数:{index.total_files}\n目录数:{index.total_dirs}",
                    layer="semantic",
                    tags=["目录索引", "README", Path(dir_path).name],
                    metadata={
                        "directory_path": dir_path,
                        "content_hash": index.content_hash,
                    },
                )
            except Exception:
                pass

        return readme_content

    def batch_generate(
        self, root_path: str, skip_dirs: set = None, max_depth: int = 2
    ) -> Dict[str, str]:
        """批量为所有子目录生成README.md"""
        if skip_dirs is None:
            skip_dirs = DirectoryScanner.SKIP_DIRS

        results = {}
        root = Path(root_path)

        for dirpath in root.rglob("*"):
            if not dirpath.is_dir():
                continue
            if dirpath.name in skip_dirs or dirpath.name.startswith("."):
                continue

            # 计算相对深度
            rel_depth = len(dirpath.relative_to(root).parts)
            if rel_depth > max_depth:
                continue

            try:
                readme = self.scan_and_generate(
                    str(dirpath), max_depth=1, save_to_file=True
                )
                results[str(dirpath)] = "SUCCESS"
            except Exception as e:
                results[str(dirpath)] = f"ERROR: {e}"

        return results

    def update_section(
        self, dir_path: str, section_name: str, new_content: str
    ) -> bool:
        """更新README.md的指定区块"""
        readme_path = Path(dir_path) / "README.md"
        if not readme_path.exists():
            return False

        try:
            content = readme_path.read_text(encoding="utf-8")
            updated = self._generator.update_readme_section(
                content, section_name, new_content
            )
            readme_path.write_text(updated, encoding="utf-8")
            return True
        except Exception:
            return False


class AIHookExecutor:
    """AI钩子执行器 - 执行README中定义的自动化任务"""

    def __init__(self, engine=None):
        self._engine = engine
        self._hook_handlers = {
            "on_open": self._handle_on_open,
            "on_change": self._handle_on_change,
            "on_create": self._handle_on_create,
            "on_delete": self._handle_on_delete,
            "on_build": self._handle_on_build,
        }

    def parse_hooks_from_readme(self, readme_path: str) -> List[AIHook]:
        """从README.md解析AI钩子"""
        hooks = []
        try:
            content = Path(readme_path).read_text(encoding="utf-8")
            lines = content.split("\n")

            for i, line in enumerate(lines):
                if "<!-- AI-HOOK:" in line:
                    match = (
                        line.strip()
                        .replace("<!-- AI-HOOK:", "")
                        .replace("-->", "")
                        .strip()
                    )
                    if match:
                        # 查找下一行作为action
                        action = lines[i + 1].strip() if i + 1 < len(lines) else ""
                        hooks.append(
                            AIHook(
                                hook_name=match,
                                trigger=match,
                                action=action,
                                description=f"Auto-detected hook: {match}",
                            )
                        )
        except Exception:
            pass
        return hooks

    def execute_hook(self, hook: AIHook, context: Dict[str, Any] = None) -> bool:
        """执行单个钩子"""
        handler = self._hook_handlers.get(hook.hook_name)
        if handler:
            try:
                return handler(hook, context or {})
            except Exception:
                return False
        return False

    def _handle_on_open(self, hook: AIHook, context: Dict) -> bool:
        """处理on_open钩子"""
        # 记录到天机
        if self._engine:
            try:
                self._engine.remember(
                    content=f"【钩子执行】on_open: {hook.action}",
                    layer="working",
                    tags=["AI钩子", "on_open"],
                )
            except Exception:
                pass
        return True

    def _handle_on_change(self, hook: AIHook, context: Dict) -> bool:
        """处理on_change钩子 - 触发README更新"""
        dir_path = context.get("dir_path")
        if dir_path:
            integrator = TianjiREADMEIntegrator(self._engine)
            integrator.scan_and_generate(dir_path, save_to_file=True)
        return True

    def _handle_on_create(self, hook: AIHook, context: Dict) -> bool:
        """处理on_create钩子"""
        return True

    def _handle_on_delete(self, hook: AIHook, context: Dict) -> bool:
        """处理on_delete钩子"""
        return True

    def _handle_on_build(self, hook: AIHook, context: Dict) -> bool:
        """处理on_build钩子"""
        return True


class AutoREADMEManager:
    """自动README管理器 - 守护进程式自动维护"""

    def __init__(self, engine=None, registry=None):
        self._integrator = TianjiREADMEIntegrator(engine, registry)
        self._hook_executor = AIHookExecutor(engine)
        self._watch_paths = []
        self._running = False

    def watch_directory(self, dir_path: str):
        """添加监控目录"""
        if Path(dir_path).exists():
            self._watch_paths.append(dir_path)

    def start_auto_update(self, interval_seconds: int = 300):
        """启动自动更新（守护进程模式）"""
        import threading

        self._running = True

        def _update_loop():
            while self._running:
                for path in self._watch_paths:
                    try:
                        self._integrator.scan_and_generate(path, save_to_file=True)
                    except Exception:
                        pass
                time.sleep(interval_seconds)

        thread = threading.Thread(target=_update_loop, daemon=True)
        thread.start()

    def stop_auto_update(self):
        """停止自动更新"""
        self._running = False

    def trigger_update(self, dir_path: str, event_type: str = "on_change"):
        """触发更新事件"""
        if event_type == "on_change":
            self._integrator.scan_and_generate(dir_path, save_to_file=True)

        # 执行钩子
        readme_path = Path(dir_path) / "README.md"
        if readme_path.exists():
            hooks = self._hook_executor.parse_hooks_from_readme(str(readme_path))
            for hook in hooks:
                if hook.hook_name == event_type:
                    self._hook_executor.execute_hook(hook, {"dir_path": dir_path})
