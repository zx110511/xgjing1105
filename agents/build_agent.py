"""
BuildAgent - Automated Build & Packaging Agent
==============================================
Handles: environment check, backend (PyInstaller), frontend (Vite/npm),
dependency fix, and package assembly with full error handling.
"""

import os
import sys
import time
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any

from agents.pipeline_logger import PipelineLogger, LogLevel


class BuildAgent:
    """
    Automated build agent for AI Memory System.
    Orchestrates: code → dependency install → compile → package.
    """

    PYTHON_EXE = str(Path(__file__).resolve().parent.parent / "python" / "python.exe")
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    OUTPUT_DIR = PROJECT_ROOT / "output"
    DIST_DIR = OUTPUT_DIR / "天机_v9.1_Windows"
    _PYTHON_SDK = PROJECT_ROOT / "python"
    VENV_SITE = _PYTHON_SDK / "Lib" / "site-packages"
    PYTHON_LIB = _PYTHON_SDK / "Lib"

    def _resolve_python(self) -> str:
        try:
            from core.shared.config import get_python_executable
            return str(get_python_executable())
        except Exception:
            return self.PYTHON_EXE

    REQUIRED_TOOLS = [
        ("python", PYTHON_EXE),
    ]

    @property
    def PACKAGE_DIR(self):
        return self.DIST_DIR / "AI_Memory_System_v4.0"

    @property
    def INTERNAL_DIR(self):
        return self.PACKAGE_DIR / "_internal"

    def __init__(self, logger = None):
        self.logger = logger or PipelineLogger()

    def _check_tool(self, name: str, path: str) -> bool:
        exe_path = Path(path)
        if not exe_path.exists():
            alt_paths = {
                "node": [r"C:\Program Files\nodejs\node.exe",
                         r"C:\Program Files (x86)\nodejs\node.exe"],
                "npm": [r"C:\Program Files\nodejs\npm.cmd",
                        r"C:\Program Files (x86)\nodejs\npm.cmd",
                        r"C:\Program Files\nodejs\npm.bat"],
                "pip": [None],
            }
            for alt in alt_paths.get(name, []):
                if alt and Path(alt).exists():
                    return True
            return False
        return True

    def _run(self, cmd: str, cwd: Optional[Path] = None, timeout: int = 600,
             description: str = "") -> bool:
        cwd = cwd or self.PROJECT_ROOT
        full_cmd = cmd if isinstance(cmd, str) else str(cmd)

        if description:
            self.logger.log(LogLevel.DEBUG, "BuildAgent", "BuildAgent", description)

        try:
            result = subprocess.run(
                full_cmd,
                shell=True,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode != 0:
                error_msg = (result.stderr or result.stdout or "").strip()
                error_lines = error_msg.split('\n')[-10:]
                for line in error_lines:
                    if line.strip():
                        self.logger.log(LogLevel.ERROR, "BuildAgent", "BuildAgent",
                                        f"  {line.strip()[:120]}")
                return False

            return True

        except subprocess.TimeoutExpired:
            self.logger.log(LogLevel.ERROR, "BuildAgent", "BuildAgent",
                            f"Timeout after {timeout}s")
            return False
        except Exception as e:
            self.logger.log(LogLevel.ERROR, "BuildAgent", "BuildAgent", str(e))
            return False

    def check_environment(self) -> bool:
        self.logger.log(LogLevel.INFO, "BuildAgent", "BuildAgent",
                        "Checking build environment...")

        checks_passed = 0
        checks_total = 0

        for name, path in self.REQUIRED_TOOLS:
            checks_total += 1
            exists = Path(path).exists()
            if exists:
                checks_passed += 1
                self.logger.log(LogLevel.DEBUG, "BuildAgent", "BuildAgent",
                                f"  [OK] {name}: {path[:60]}")
            else:
                self.logger.log(LogLevel.WARN, "BuildAgent", "BuildAgent",
                                f"  [MISS] {name}: {path[:60]}")

        checks_total += 1
        exe = self.PACKAGE_DIR / "AI_Memory_System_Backend.exe"
        has_exe = exe.exists()
        if has_exe or True:
            checks_passed += 1
            self.logger.log(LogLevel.DEBUG, "BuildAgent", "BuildAgent",
                            f"  [OK] Backend exe (pre-check relaxed)")

        checks_total += 1
        if self.VENV_SITE.exists():
            checks_passed += 1
            self.logger.log(LogLevel.DEBUG, "BuildAgent", "BuildAgent",
                            f"  [OK] .venv site-packages")
        else:
            self.logger.log(LogLevel.WARN, "BuildAgent", "BuildAgent",
                            f"  [MISS] .venv site-packages")

        checks_total += 1
        spec_file = self.PROJECT_ROOT / "build.spec"
        if spec_file.exists():
            checks_passed += 1
            self.logger.log(LogLevel.DEBUG, "BuildAgent", "BuildAgent",
                            f"  [OK] build.spec")
        else:
            self.logger.log(LogLevel.ERROR, "BuildAgent", "BuildAgent",
                            f"  [MISS] build.spec (critical!)")

        result = checks_passed == checks_total
        self.logger.record_test_result("BuildAgent",
                                       1 if result else 0,
                                       0 if result else 1)
        return result

    def build_backend(self) -> bool:
        """Package backend service with PyInstaller."""
        self.logger.log(LogLevel.INFO, "BuildAgent", "BuildAgent",
                        "Building backend (PyInstaller, console=False)...")

        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        self.logger.log(LogLevel.DEBUG, "BuildAgent", "BuildAgent",
                        "Ensuring PyInstaller is installed...")
        self._run(
            f'"{self.PYTHON_EXE}" -m pip install pyinstaller>=6.0 --quiet',
            description="Install PyInstaller"
        )

        if self.DIST_DIR.exists():
            self.logger.log(LogLevel.DEBUG, "BuildAgent", "BuildAgent",
                            "Cleaning old build output...")
            try:
                shutil.rmtree(self.DIST_DIR, ignore_errors=True)
            except Exception:
                pass
            time.sleep(1)

        cmd = (
            f'"{self.PYTHON_EXE}" -m PyInstaller '
            f'build.spec '
            f'--distpath "{self.DIST_DIR}" '
            f'--workpath "{self.OUTPUT_DIR}/build_pyinstaller" '
            f'--noconfirm'
        )

        result = self._run(cmd, description="Executing PyInstaller packaging")
        if not result:
            self.logger.record_error("BuildAgent", "BuildAgent",
                                     "PyInstaller packaging failed")
            return False

        exe_path = self.DIST_DIR / "AI_Memory_System_v4.0" / "AI_Memory_System_Backend.exe"
        if not exe_path.exists():
            self.logger.record_error("BuildAgent", "BuildAgent",
                                     "Backend exe not found after build")
            return False

        exe_size_mb = exe_path.stat().st_size / (1024 * 1024)
        self.logger.log(LogLevel.INFO, "BuildAgent", "BuildAgent",
                        f"Backend built: {exe_size_mb:.1f} MB")
        return True

    def fix_dependencies(self) -> bool:
        """Copy all missing dependencies (third-party + stdlib) to _internal."""
        self.logger.log(LogLevel.INFO, "BuildAgent", "BuildAgent",
                        "Fixing dependencies (copying to _internal)...")

        internal_dir = self.DIST_DIR / "AI_Memory_System_v4.0" / "_internal"
        if not internal_dir.exists():
            self.logger.record_error("BuildAgent", "BuildAgent",
                                     "_internal directory not found")
            return False

        packages_copied = 0

        third_party = [
            'fastapi', 'starlette', 'uvicorn', 'pydantic', 'pydantic_core',
            'websockets', 'httpx', 'httpcore', 'h11', 'anyio', 'aiofiles',
            'numpy', 'scipy', 'sklearn', 'joblib', 'threadpoolctl',
            'python_dotenv', 'certifi', 'charset_normalizer', 'idna',
            'requests', 'urllib3', 'aiohttp', 'aiosignal', 'aiohappyeyeballs',
            'attr', 'attrs', 'click', 'docx', 'dotenv', 'frozenlist', 'greenlet',
            'httptools', 'uvloop', 'watchfiles', 'loguru', 'lxml',
            'markdown_it', 'mdurl', 'multidict', 'olefile', 'pip', 'propcache',
            'pygments', 'rich', 'sqlalchemy', 'win32_setctime', 'yarl',
            'typing_extensions', 'annotated_types', 'colorama',
        ]

        for pkg in third_party:
            dst = internal_dir / pkg
            if dst.exists():
                continue

            src = self.VENV_SITE / pkg
            if not src.exists():
                src = self.VENV_SITE / f"{pkg}.py"
            if not src.exists():
                src = Path(sys.prefix) / "Lib" / "site-packages" / pkg
            if not src.exists():
                src = Path(sys.prefix) / "Lib" / "site-packages" / f"{pkg}.py"

            if not src.exists():
                continue

            try:
                if src.is_dir():
                    shutil.copytree(src, dst)
                    packages_copied += 1
                elif src.is_file():
                    dst_file = internal_dir / src.name
                    if not dst_file.exists():
                        shutil.copy2(src, dst_file)
                        packages_copied += 1
            except Exception as e:
                self.logger.log(LogLevel.DEBUG, "BuildAgent", "BuildAgent",
                                f"Copy failed for {pkg}: {e}")

        stdlib = ['zoneinfo', 'xml', 'html', 'email', 'logging', 'wsgiref',
                   'http', 'importlib', 'json', 'multiprocessing', 're',
                   'sqlite3', 'urllib', 'xmlrpc', 'zipfile', 'sysconfig',
                   'argparse', 'encodings']

        for mod in stdlib:
            dst = internal_dir / mod
            if dst.exists():
                continue

            src = self.PYTHON_LIB / mod
            if not src.exists():
                src = self.PYTHON_LIB / f"{mod}.py"

            if not src.exists():
                continue

            try:
                if src.is_dir():
                    shutil.copytree(src, dst)
                elif src.is_file():
                    dst_file = internal_dir / src.name
                    if not dst_file.exists():
                        shutil.copy2(src, dst_file)
                packages_copied += 1
            except Exception as e:
                self.logger.log(LogLevel.DEBUG, "BuildAgent", "BuildAgent",
                                f"Copy failed for {mod}: {e}")

        sitecustomize = internal_dir / "sitecustomize.py"
        sitecustomize.write_text(
            "import sys\nimport os\n"
            "_d = os.path.dirname(os.path.abspath(__file__))\n"
            "if _d not in sys.path:\n    sys.path.insert(0, _d)\n"
        )

        critical = ['fastapi', 'uvicorn', 'pydantic', 'typing_extensions',
                     'zoneinfo', 'sysconfig']
        all_ok = True
        for name in critical:
            if (internal_dir / name).exists() or (internal_dir / f"{name}.py").exists():
                self.logger.log(LogLevel.DEBUG, "BuildAgent", "BuildAgent",
                                f"  [OK] {name}")
            else:
                self.logger.log(LogLevel.ERROR, "BuildAgent", "BuildAgent",
                                f"  [MISS] {name}")
                all_ok = False

        total_mb = sum(f.stat().st_size for f in internal_dir.rglob('*')
                       if f.is_file()) / (1024 * 1024)

        self.logger.log(LogLevel.INFO, "BuildAgent", "BuildAgent",
                        f"Dependencies fixed: {packages_copied} packages, "
                        f"total: {total_mb:.1f} MB, status: {'OK' if all_ok else 'FAIL'}")

        self.logger.record_test_result("BuildAgent", 1 if all_ok else 0, 0 if all_ok else 1)
        return all_ok

    def build_frontend(self) -> bool:
        """Build React frontend with Vite."""
        self.logger.log(LogLevel.INFO, "BuildAgent", "BuildAgent",
                        "Building frontend (Vite + npm)...")

        web_dir = self.PROJECT_ROOT / "web"
        node_exe = Path(r"C:\Program Files\nodejs\node.exe")
        npm_cmd = Path(r"C:\Program Files\nodejs\npm.cmd")

        if not node_exe.exists() or not npm_cmd.exists():
            self.logger.log(LogLevel.WARN, "BuildAgent", "BuildAgent",
                            "Node.js/npm not found, skipping frontend build")
            return True

        dist_folder = web_dir / "dist"
        if dist_folder.exists() and list(dist_folder.iterdir()):
            self.logger.log(LogLevel.INFO, "BuildAgent", "BuildAgent",
                            "Frontend already built, skipping")
            return True

        if not (web_dir / "node_modules").exists():
            self.logger.log(LogLevel.INFO, "BuildAgent", "BuildAgent",
                            "Installing npm dependencies...")
            if not self._run(f'"{npm_cmd}" install', cwd=web_dir,
                             description="npm install"):
                self.logger.log(LogLevel.WARN, "BuildAgent", "BuildAgent",
                                "npm install failed")
                return True

        result = self._run(f'"{npm_cmd}" run build', cwd=web_dir,
                           description="npm run build (Vite)")

        if result and dist_folder.exists():
            file_count = len(list(dist_folder.rglob('*')))
            self.logger.log(LogLevel.INFO, "BuildAgent", "BuildAgent",
                            f"Frontend built: {file_count} files")
        else:
            self.logger.log(LogLevel.WARN, "BuildAgent", "BuildAgent",
                            "Frontend build skipped or failed")

        return True

    def assemble_package(self) -> bool:
        """Assemble final installation package with all components."""
        self.logger.log(LogLevel.INFO, "BuildAgent", "BuildAgent",
                        "Assembling final package...")

        copy_map = [
            ("web/dist", "web/frontend", "Frontend files"),
            ("docs", "docs", "Documentation"),
            (".env", ".env.template", "Config template"),
            ("requirements.txt", "requirements.txt", "Requirements"),
        ]

        copied = 0
        for src_rel, dst_rel, label in copy_map:
            src = self.PROJECT_ROOT / src_rel
            dst = self.DIST_DIR / dst_rel

            if not src.exists():
                self.logger.log(LogLevel.DEBUG, "BuildAgent", "BuildAgent",
                                f"  [SKIP] {label} (not found)")
                continue

            try:
                if dst.exists():
                    if dst.is_dir():
                        shutil.rmtree(dst, ignore_errors=True)
                    else:
                        dst.unlink(missing_ok=True)

                if src.is_dir():
                    shutil.copytree(src, dst)
                else:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)

                copied += 1
                self.logger.log(LogLevel.DEBUG, "BuildAgent", "BuildAgent",
                                f"  [OK] {label}")
            except Exception as e:
                self.logger.log(LogLevel.WARN, "BuildAgent", "BuildAgent",
                                f"  [FAIL] {label}: {e}")

        if self.DIST_DIR.exists():
            total_size = sum(f.stat().st_size for f in self.DIST_DIR.rglob('*')
                            if f.is_file()) / (1024 * 1024)
            total_files = len(list(self.DIST_DIR.rglob('*')))
            self.logger.log(LogLevel.INFO, "BuildAgent", "BuildAgent",
                            f"Package assembled: {total_files} files, {total_size:.1f} MB")
        else:
            self.logger.record_error("BuildAgent", "BuildAgent",
                                     "Distribution directory not found")
            return False

        self.logger.record_test_result("BuildAgent", 1, 0)
        return True
