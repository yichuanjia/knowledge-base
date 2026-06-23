"""AI 知识库助手 — 采集入口。

运行方式：python -m pipeline.main
"""

import logging
import sys
from pathlib import Path

from pipeline.collector import run

LOG_DIR = Path("logs")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def _setup_logging() -> None:
    """初始化日志系统，输出到 logs/ 目录和终端。"""
    LOG_DIR.mkdir(exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    file_handler = logging.FileHandler(
        LOG_DIR / "pipeline.log", encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root_logger.addHandler(console_handler)


if __name__ == "__main__":
    _setup_logging()
    results = run()

    if not results:
        logging.getLogger(__name__).warning("未采集到任何数据，请检查网络或 API 限速")
        sys.exit(1)

    for source, filepath in results.items():
        print(f"[OK] {source} → {filepath}")
