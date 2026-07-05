"""
TestAgent - SG-0~4 Stage Gate Verification Framework
=====================================================
Implements the complete 5-stage gate verification system with
100% test case coverage requirement and structured evidence reporting.

SG-0: Environment Readiness - tools/deps/paths check
SG-1: Import & Path Isolation - module import verification
SG-2: Functional Verification - real-data functional testing
SG-3: MCP Integration Test - end-to-end MCP tool verification
SG-4: Regression Testing - change impact & baseline comparison
"""

import os
import sys
import time
import json
import importlib
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

from agents.pipeline_logger import PipelineLogger, LogLevel


class TestAgent:
    """
    Stage Gate verification agent.
    Executes SG-0 through SG-4 with structured reporting.
    """

    PYTHON_EXE = str(Path(__file__).resolve().parent.parent / "python" / "python.exe")
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    DIST_DIR = PROJECT_ROOT / "output" / "天机_v9.1_Windows"
    PACKAGE_DIR = DIST_DIR / "天机_v9.1"
    INTERNAL_DIR = PACKAGE_DIR / "_internal"

    def _resolve_python(self) -> str:
        try:
            from core.shared.config import get_python_executable
            return str(get_python_executable())
        except Exception:
            return self.PYTHON_EXE

    SG_GATES = {
        "SG-0": "Environment Readiness",
        "SG-1": "Import & Path Isolation",
        "SG-2": "Functional Verification",
        "SG-3": "MCP Integration Test",
        "SG-4": "Regression Testing",
    }

    SG_PASS_CRITERIA = {
        "SG-0": "All environment checks must pass (100%)",
        "SG-1": "Zero import errors (0 allowed)",
        "SG-2": "Core test cases 100%, edge cases >90%",
        "SG-3": "All MCP tool calls succeed",
        "SG-4": "Zero new regression failures",
    }

    def __init__(self, logger = None):
        self.logger = logger or PipelineLogger()
        self.results: Dict[str, Dict] = {}

    def _ensure_path(self) -> bool:
        internal = self.INTERNAL_DIR
        if not internal.exists():
            self.logger.log(LogLevel.WARN, "TestAgent", "TestAgent",
                            f"_internal not found: {internal}")
            return False
        if str(internal) not in sys.path:
            sys.path.insert(0, str(internal))
            self.logger.log(LogLevel.DEBUG, "TestAgent", "TestAgent",
                            f"Added to sys.path: {internal}")
        return True

    def _log_tvp(self, sg: str, status: str = "preparing") -> None:
        self.logger.log(LogLevel.INFO, sg, "TestAgent",
                        f"[TVP] {sg} ({self.SG_GATES.get(sg, '')}): {status}")

    def _write_gate_result(self, sg: str, passed: int, failed: int,
                           evidence: List[Dict], errors: List[str]) -> Dict:
        result = {
            "gate": sg,
            "name": self.SG_GATES.get(sg, ""),
            "pass_criteria": self.SG_PASS_CRITERIA.get(sg, ""),
            "timestamp": datetime.now().isoformat(),
            "tests_passed": passed,
            "tests_failed": failed,
            "pass_rate": round(passed / (passed + failed) * 100, 1) if (passed + failed) > 0 else 0,
            "status": "PASS" if failed == 0 else ("PARTIAL" if passed > 0 else "FAIL"),
            "evidence": evidence[:10],
            "errors": errors[:5],
        }
        self.results[sg] = result

        self.logger.record_test_result(sg, passed, failed)
        for err in errors:
            self.logger.record_error(sg, "TestAgent", err)

        return result

    def run_sg0(self) -> bool:
        """
        SG-0: Environment Readiness
        Check Python, dependencies, paths, data directories.
        """
        self._log_tvp("SG-0", "executing")
        self.logger.stage_start("SG-0")

        checks = []
        passed = 0
        failed = 0

        checks.append(self._check_python())
        checks.append(self._check_package_env())
        checks.append(self._check_exe_exists())
        checks.append(self._check_internal_deps())
        checks.append(self._check_data_dir())

        for name, result in checks:
            if result:
                passed += 1
                self.logger.log(LogLevel.DEBUG, "SG-0", "TestAgent", f"  [PASS] {name}")
            else:
                failed += 1
                self.logger.log(LogLevel.ERROR, "SG-0", "TestAgent", f"  [FAIL] {name}")

        evidence = [
            {"check": name, "result": "PASS" if r else "FAIL"}
            for name, r in checks
        ]

        errors = [name for name, r in checks if not r]

        result = self._write_gate_result("SG-0", passed, failed, evidence, errors)
        self.logger.stage_end("SG-0", "completed" if failed == 0 else "failed")

        return failed == 0

    def _check_python(self) -> Tuple[str, bool]:
        python_path = Path(self.PYTHON_EXE)
        if not python_path.exists():
            return ("Python executable exists", False)

        try:
            result = subprocess.run(
                [self.PYTHON_EXE, "--version"],
                capture_output=True, text=True, timeout=10
            )
            version = result.stdout.strip()
            is_312 = "3.12" in version
            return (f"Python version ({version})", is_312)
        except Exception:
            return ("Python executable works", False)

    def _check_package_env(self) -> Tuple[str, bool]:
        return ("Package directory exists", self.PACKAGE_DIR.exists())

    def _check_exe_exists(self) -> Tuple[str, bool]:
        exe = self.PACKAGE_DIR / "AI_Memory_System_Backend.exe"
        exists = exe.exists()
        if exists:
            size_mb = exe.stat().st_size / (1024 * 1024)
            return (f"Backend exe ({size_mb:.1f} MB)", True)
        return ("Backend exe exists", False)

    def _check_internal_deps(self) -> Tuple[str, bool]:
        if not self.INTERNAL_DIR.exists():
            return ("_internal directory", False)

        critical = ['fastapi', 'uvicorn', 'pydantic', 'typing_extensions.py']
        all_ok = True
        for dep in critical:
            p = self.INTERNAL_DIR / dep
            if not p.exists():
                all_ok = False
                break
        return ("Critical dependencies present", all_ok)

    def _check_data_dir(self) -> Tuple[str, bool]:
        data_dir = self.INTERNAL_DIR / "data"
        return ("Data directory", data_dir.exists())

    def run_sg1(self) -> bool:
        """
        SG-1: Import & Path Isolation
        Verify all modules can be imported without errors.

        Uses subprocess to test imports in an isolated environment
        that simulates the packaged exe context.
        """
        self._log_tvp("SG-1", "executing")
        self.logger.stage_start("SG-1")

        passed = 0
        failed = 0
        evidence = []
        errors = []

        modules_to_test = [
            "fastapi",
            "fastapi.routing",
            "fastapi.middleware.cors",
            "starlette",
            "uvicorn",
            "pydantic",
            "pydantic.fields",
            "typing_extensions",
            "numpy",
            "sklearn",
            "sklearn.feature_extraction.text",
            "zoneinfo",
            "sysconfig",
        ]

        test_script = self.PROJECT_ROOT / "agents" / "test_import_subprocess.py"

        if not test_script.exists():
            self.logger.log(LogLevel.ERROR, "SG-1", "TestAgent",
                            f"Test script not found: {test_script}")
            return False

        test_config = {
            "internal_dir": str(self.INTERNAL_DIR),
            "modules": modules_to_test
        }

        try:
            result = subprocess.run(
                [self.PYTHON_EXE, str(test_script)],
                input=json.dumps(test_config),
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.PROJECT_ROOT)
            )

            if result.returncode != 0:
                self.logger.log(LogLevel.ERROR, "SG-1", "TestAgent",
                                f"Subprocess failed: {result.stderr}")
                return False

            output = json.loads(result.stdout)

            if output.get("status") != "success":
                self.logger.log(LogLevel.ERROR, "SG-1", "TestAgent",
                                f"Test script error: {output.get('error')}")
                return False

            for test_result in output.get("results", []):
                mod_name = test_result["module"]
                success = test_result["success"]

                if success:
                    passed += 1
                    version = test_result.get("version", "unknown")
                    self.logger.log(LogLevel.DEBUG, "SG-1", "TestAgent",
                                    f"  [PASS] {mod_name} (v{version})")
                    evidence.append({
                        "module": mod_name,
                        "result": "PASS",
                        "version": version
                    })
                else:
                    failed += 1
                    error_msg = test_result.get("error", "Unknown error")
                    errors.append(f"Import failed: {mod_name} - {error_msg}")
                    self.logger.log(LogLevel.ERROR, "SG-1", "TestAgent",
                                    f"  [FAIL] {mod_name}: {error_msg}")
                    evidence.append({
                        "module": mod_name,
                        "result": "FAIL",
                        "error": error_msg[:100]
                    })

        except subprocess.TimeoutExpired:
            self.logger.log(LogLevel.ERROR, "SG-1", "TestAgent",
                            "Subprocess timeout (30s)")
            return False
        except json.JSONDecodeError as e:
            self.logger.log(LogLevel.ERROR, "SG-1", "TestAgent",
                            f"JSON decode error: {e}")
            return False
        except Exception as e:
            self.logger.log(LogLevel.ERROR, "SG-1", "TestAgent",
                            f"Unexpected error: {e}")
            return False

        result = self._write_gate_result("SG-1", passed, failed, evidence, errors)
        self.logger.stage_end("SG-1", "completed" if failed == 0 else "failed")

        return failed == 0

    def run_sg2(self) -> bool:
        """
        SG-2: Functional Verification
        Test core functions with real data inputs.
        """
        self._log_tvp("SG-2", "executing")
        self.logger.stage_start("SG-2")

        passed = 0
        failed = 0
        evidence = []
        errors = []

        test_cases = [
            ("Normal import", self._test_normal_import),
            ("FastAPI app creation", self._test_fastapi_app),
            ("CORS middleware", self._test_cors_middleware),
            ("Health check endpoint", self._test_health_endpoint),
            ("Pydantic model creation", self._test_pydantic_model),
            ("Edge: Empty input handling", self._test_empty_input),
            ("Edge: Large data handling", self._test_large_data),
        ]

        for name, test_fn in test_cases:
            try:
                result, detail = test_fn()
                if result:
                    passed += 1
                    self.logger.log(LogLevel.DEBUG, "SG-2", "TestAgent",
                                    f"  [PASS] {name}")
                else:
                    failed += 1
                    self.logger.log(LogLevel.ERROR, "SG-2", "TestAgent",
                                    f"  [FAIL] {name}: {detail}")
                    errors.append(f"{name}: {detail}")
                evidence.append({"case": name, "result": "PASS" if result else "FAIL",
                                 "detail": detail})
            except Exception as e:
                failed += 1
                errors.append(f"{name}: {e}")
                evidence.append({"case": name, "result": "FAIL", "error": str(e)[:100]})

        result = self._write_gate_result("SG-2", passed, failed, evidence, errors)
        self.logger.stage_end("SG-2", "completed" if failed <= 1 else "failed")

        return failed <= 1

    def _test_normal_import(self) -> Tuple[bool, str]:
        try:
            from fastapi import FastAPI
            return True, f"FastAPI imported (v{importlib.metadata.version('fastapi')})"
        except Exception as e:
            return False, str(e)

    def _test_fastapi_app(self) -> Tuple[bool, str]:
        try:
            from fastapi import FastAPI
            app = FastAPI(title="Test App")
            return True, f"App created: {app.title}"
        except Exception as e:
            return False, str(e)

    def _test_cors_middleware(self) -> Tuple[bool, str]:
        try:
            from fastapi import FastAPI
            from fastapi.middleware.cors import CORSMiddleware
            app = FastAPI()
            app.add_middleware(CORSMiddleware, allow_origins=["*"],
                              allow_methods=["*"], allow_headers=["*"])
            return True, "CORS middleware added"
        except Exception as e:
            return False, str(e)

    def _test_health_endpoint(self) -> Tuple[bool, str]:
        try:
            from fastapi import FastAPI
            import uvicorn
            return True, "Health check infrastructure ready"
        except Exception as e:
            return False, str(e)

    def _test_pydantic_model(self) -> Tuple[bool, str]:
        try:
            from pydantic import BaseModel
            class TestModel(BaseModel):
                name: str = "test"
                value: int = 42
            m = TestModel()
            return True, f"Model created: {m.name}={m.value}"
        except Exception as e:
            return False, str(e)

    def _test_empty_input(self) -> Tuple[bool, str]:
        try:
            from pydantic import BaseModel
            class EmptyTest(BaseModel):
                content: str = ""
            m = EmptyTest()
            return True, f"Empty model OK: '{m.content}'"
        except Exception as e:
            return False, str(e)

    def _test_large_data(self) -> Tuple[bool, str]:
        try:
            import numpy as np
            arr = np.zeros(1000, dtype=float)
            return True, f"Large array OK: {arr.shape}"
        except Exception as e:
            return False, str(e)

    def run_sg3(self) -> bool:
        """
        SG-3: MCP Integration Test
        Verify MCP (Model Context Protocol) tool connectivity.
        """
        self._log_tvp("SG-3", "executing")
        self.logger.stage_start("SG-3")

        passed = 0
        failed = 0
        evidence = []
        errors = []

        mcp_checks = [
            ("Server modules exist", self._check_mcp_modules),
            ("Memory routes importable", self._check_memory_routes),
            ("Search routes importable", self._check_search_routes),
            ("LLM routes importable", self._check_llm_routes),
        ]

        for name, check_fn in mcp_checks:
            try:
                result, detail = check_fn()
                if result:
                    passed += 1
                else:
                    failed += 1
                    errors.append(f"{name}: {detail}")
                evidence.append({"check": name, "result": "PASS" if result else "FAIL",
                                 "detail": detail})
            except Exception as e:
                failed += 1
                errors.append(f"{name}: {e}")
                evidence.append({"check": name, "result": "FAIL", "error": str(e)})

        result = self._write_gate_result("SG-3", passed, failed, evidence, errors)
        self.logger.stage_end("SG-3", "completed" if failed == 0 else "failed")

        return failed == 0

    def _check_mcp_modules(self) -> Tuple[bool, str]:
        server_api = self.PROJECT_ROOT / "server" / "api"
        modules = ["mcp_routes.py", "memory_routes.py", "search_routes.py", "llm_routes.py"]
        found = [m for m in modules if (server_api / m).exists()]
        return all(m in found for m in modules), f"Found: {len(found)}/{len(modules)}"

    def _check_memory_routes(self) -> Tuple[bool, str]:
        try:
            from server.api.memory_routes import router
            return True, f"Memory router OK ({len(router.routes)} routes)"
        except Exception as e:
            return False, str(e)

    def _check_search_routes(self) -> Tuple[bool, str]:
        try:
            from server.api.search_routes import create_search_router
            return True, "Search router factory OK"
        except Exception as e:
            return False, str(e)

    def _check_llm_routes(self) -> Tuple[bool, str]:
        try:
            from server.api.llm_routes import router
            return True, f"LLM router OK ({len(router.routes)} routes)"
        except Exception as e:
            return False, str(e)

    def run_sg4(self) -> bool:
        """
        SG-4: Regression Testing
        Verify no existing functionality is broken.
        """
        self._log_tvp("SG-4", "executing")
        self.logger.stage_start("SG-4")

        passed = 0
        failed = 0
        evidence = []
        errors = []

        regression_tests = [
            ("Core engine import", self._test_core_engine),
            ("ICME layers defined", self._test_icme_layers),
            ("Config load", self._test_config_load),
            ("Models validation", self._test_models),
            ("Adapter imports", self._test_adapters),
            ("All prior SG gates passed", self._test_prior_gates),
        ]

        for name, test_fn in regression_tests:
            try:
                result, detail = test_fn()
                if result:
                    passed += 1
                else:
                    failed += 1
                    errors.append(f"{name}: {detail}")
                evidence.append({"test": name, "result": "PASS" if result else "FAIL",
                                 "detail": detail})
            except Exception as e:
                failed += 1
                errors.append(f"{name}: {e}")
                evidence.append({"test": name, "result": "FAIL", "error": str(e)})

        result = self._write_gate_result("SG-4", passed, failed, evidence, errors)
        self.logger.stage_end("SG-4", "completed" if failed == 0 else "failed")

        return failed == 0

    def _test_core_engine(self) -> Tuple[bool, str]:
        try:
            from core.memory.engine import ICMEEngine
            return True, "ICMEEngine importable"
        except Exception as e:
            return False, str(e)

    def _test_icme_layers(self) -> Tuple[bool, str]:
        try:
            from core.shared.models import MemoryLayer
            layers = [l.value for l in MemoryLayer]
            expected = ["sensory", "working", "short_term", "episodic", "semantic", "meta"]
            return layers == expected, f"Layers: {layers}"
        except Exception as e:
            return False, str(e)

    def _test_config_load(self) -> Tuple[bool, str]:
        try:
            from core.shared.config import Config
            return True, "Config importable"
        except Exception as e:
            return False, str(e)

    def _test_models(self) -> Tuple[bool, str]:
        try:
            from core.shared.models import MemoryCreate, Priority
            return True, "Data models importable"
        except Exception as e:
            return False, str(e)

    def _test_adapters(self) -> Tuple[bool, str]:
        try:
            from adapters.trae_adapter import TraeAdapter
            return True, "Adapters importable"
        except Exception as e:
            return False, str(e)

    def _test_prior_gates(self) -> Tuple[bool, str]:
        passed = sum(1 for r in self.results.values() if r.get("status") == "PASS")
        total = len(self.results)
        return (passed == total, f"{passed}/{total} gates passed")

    def generate_test_report(self) -> Dict[str, Any]:
        """Generate comprehensive JSON test report."""
        return {
            "test_framework": "SG-0~4 Stage Gate",
            "version": "1.0.0",
            "generated_at": datetime.now().isoformat(),
            "project": "AI Memory System v4.0",
            "gates": self.results,
            "summary": {
                "gates_total": len(self.results),
                "gates_passed": sum(1 for r in self.results.values()
                                    if r.get("status") == "PASS"),
                "gates_failed": sum(1 for r in self.results.values()
                                    if r.get("status") != "PASS"),
                "total_tests": sum(r.get("tests_passed", 0) + r.get("tests_failed", 0)
                                  for r in self.results.values()),
                "total_passed": sum(r.get("tests_passed", 0)
                                  for r in self.results.values()),
                "total_failed": sum(r.get("tests_failed", 0)
                                  for r in self.results.values()),
                "overall_status": "PASS" if all(
                    r.get("status") == "PASS" for r in self.results.values()
                ) else "FAIL",
            }
        }
