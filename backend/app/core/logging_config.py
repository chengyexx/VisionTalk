"""
Vision Talk — 统一日志配置

在 main.py 的 lifespan 启动时调用 setup_logging() 即可全局启用。
日志同时输出到:
- 控制台 (stdout, WARNING 级别, 仅关键信息)
- 文件   (logs/vision_talk.log, DEBUG 级别, 按日轮转, 完整调试)
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
_DATE_FORMAT = "%H:%M:%S"


def setup_logging(*, level: int = logging.INFO) -> None:
    """
    初始化全局日志配置。

    典型调用 (main.py lifespan):
        from app.core.logging_config import setup_logging
        setup_logging()
    """
    root = logging.getLogger()

    # 避免重复注册 (uvicorn reload 模式下可能多次调用)
    if root.handlers:
        return

    root.setLevel(logging.DEBUG)

    # ── 控制台 handler: WARNING+ (仅错误和关键事件) ──
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.WARNING)
    console.setFormatter(logging.Formatter(_CONSOLE_FORMAT, datefmt=_DATE_FORMAT))
    root.addHandler(console)

    # ── 文件 handler: DEBUG (完整日志用于调试) ──
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

    # ── 启动信息: 单独控制台 INFO 级别 ──
    startup_console = logging.StreamHandler(sys.stdout)
    startup_console.setLevel(logging.INFO)
    startup_console.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-7s  %(message)s", datefmt=_DATE_FORMAT
    ))
    startup_console.addFilter(lambda r: r.name in ("vision_talk.main",))
    root.addHandler(startup_console)

    # ── 抑制第三方库的杂乱日志 ──
    _SILENCED = [
        "httpx", "httpcore", "urllib3", "openai",
        "uvicorn", "uvicorn.access", "uvicorn.error",
        "LiteLLM", "litellm",  # LiteLLM 自己的日志管道
    ]
    for name in _SILENCED:
        logging.getLogger(name).setLevel(logging.WARNING)

    # LiteLLM 底层 DEBUG 打印 (绕过标准 logging 的 print 输出)
    _silence_litellm()


def _silence_litellm() -> None:
    """关闭 LiteLLM 的 verbose 输出，防止打印完整消息 payload 到控制台"""
    try:
        import litellm
        litellm.set_verbose = False
        litellm.suppress_debug_info = True
    except Exception:
        pass

    # litellm._logging 模块有自己的 StreamHandler，追加抑制
    try:
        logging.getLogger("litellm._logging").setLevel(logging.WARNING)
        logging.getLogger("litellm.utils").setLevel(logging.WARNING)
        logging.getLogger("litellm.litellm_core_utils").setLevel(logging.WARNING)
    except Exception:
        pass
