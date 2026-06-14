"""
Vision Talk — 统一日志配置

在 main.py 的 lifespan 启动时调用 setup_logging() 即可全局启用。
日志同时输出到:
- 控制台 (stdout, INFO 级别, 彩色格式)
- 文件   (logs/vision_talk.log, DEBUG 级别, 按日轮转)
"""
import logging
import logging.handlers
import sys
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"

_CONSOLE_FORMAT = (
    "%(asctime)s  %(levelname)-7s  %(name)-24s  %(message)s"
)
_FILE_FORMAT = (
    "%(asctime)s  %(levelname)-7s  %(name)s:%(lineno)d  %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(*, level: int = logging.INFO) -> None:
    """
    初始化全局日志配置。

    典型调用 (main.py lifespan):
        from app.core.logging_config import setup_logging
        setup_logging(level=logging.DEBUG if DEBUG else logging.INFO)
    """
    root = logging.getLogger()

    # 避免重复注册 (uvicorn reload 模式下可能多次调用)
    if root.handlers:
        return

    root.setLevel(logging.DEBUG)

    # ── 控制台 handler ──
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(_CONSOLE_FORMAT, datefmt=_DATE_FORMAT))
    root.addHandler(console)

    # ── 文件 handler ──
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=LOG_DIR / "vision_talk.log",
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(_FILE_FORMAT, datefmt=_DATE_FORMAT))
    root.addHandler(file_handler)

    # 抑制第三方库的杂乱日志
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)

    logger = logging.getLogger("vision_talk")
    logger.info("日志系统初始化完成 (console_level=%s, file=DEBUG)", logging.getLevelName(level))
