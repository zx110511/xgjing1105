r"""
天机 (TIANJI) - Structured File Logger v1.0
=============================================
《天机·星枢运转》— 日志系统

Features:
- Rotating file handler (10MB per file, 5 backups)
- Structured JSON log format
- Console + File dual output
- Module-level logger factory
- Windows encoding safe
"""

import logging
import logging.handlers
import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Optional


TIANJI_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = TIANJI_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            log_entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[90m",
        "INFO": "\033[92m",
        "WARNING": "\033[93m",
        "ERROR": "\033[91m",
        "CRITICAL": "\033[95m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        color = self.COLORS.get(record.levelname, "")
        msg = record.getMessage()
        return f"{color}{ts} [{record.levelname:7s}]{self.RESET} {record.module} | {msg}"


class TianjiLogger:
    _loggers: dict[str, logging.Logger] = {}

    def __init__(self, name: str = "tianji", log_dir: Optional[Path] = None):
        self.name = name
        self.log_dir = log_dir or LOG_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)

        if name in TianjiLogger._loggers:
            self._logger = TianjiLogger._loggers[name]
            return

        self._logger = logging.getLogger(f"tianji.{name}")
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False

        if not self._logger.handlers:
            self._add_file_handler()
            self._add_console_handler()

        TianjiLogger._loggers[name] = self._logger

    def _add_file_handler(self):
        log_file = self.log_dir / f"{self.name}.log"
        handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(JsonFormatter())
        self._logger.addHandler(handler)

    def _add_console_handler(self):
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.INFO)
        handler.setFormatter(ConsoleFormatter())
        self._logger.addHandler(handler)

    def debug(self, msg: str, **kwargs):
        self._logger.debug(msg, **kwargs)

    def info(self, msg: str, **kwargs):
        self._logger.info(msg, **kwargs)

    def warning(self, msg: str, **kwargs):
        self._logger.warning(msg, **kwargs)

    def error(self, msg: str, **kwargs):
        self._logger.error(msg, **kwargs)

    def critical(self, msg: str, **kwargs):
        self._logger.critical(msg, **kwargs)

    def exception(self, msg: str, **kwargs):
        self._logger.exception(msg, **kwargs)


def get_logger(name: str = "tianji") -> TianjiLogger:
    return TianjiLogger(name)
