r"""
天机 (TIANJI) - Daemon Module
=================================
《天机·星枢运转》— 守护·监控·备份·修复
"""

from daemon.tianji_daemon import TianjiDaemon
from daemon.tianji_logger import get_logger, TianjiLogger

__all__ = ["TianjiDaemon", "get_logger", "TianjiLogger"]
