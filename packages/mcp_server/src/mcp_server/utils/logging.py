import logging
import sys
from functools import lru_cache
from pathlib import Path

from configs import request_id_var
from loguru import logger


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        # 安全获取当前请求ID
        try:
            current_request_id = request_id_var.get()
        except LookupError:
            current_request_id = "SYSTEM"

        with logger.contextualize(request_id_var=current_request_id):
            logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


@lru_cache
def setup_logging():
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    def patcher(record):
        """确保request_id_var字段存在."""
        record["extra"].setdefault("request_id_var", "SYSTEM")

    # 统一格式
    fmt = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | {extra[request_id_var]} | <lvl>{level}</lvl> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <lvl>{message}</lvl>"

    if list(logger._core.handlers.keys()) == [0]:
        logger.remove()

    logger.configure(patcher=patcher)

    # logger.remove()
    logger.add(sys.stdout, format=fmt, level="INFO", colorize=True)
    logger.add(log_dir / "app.log", rotation="10 MB", retention="7 days", enqueue=True, format=fmt, encoding="utf-8")
    logger.add(log_dir / "error.log", level="ERROR", rotation="10 MB", retention="7 days", enqueue=True, format=fmt, encoding="utf-8")

    # 收编三方库
    logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO, force=True)
    for name in [
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "fastapi",
        "mcp",
        "webpage_converter",
    ]:
        _log = logging.getLogger(name)
        _log.handlers = [InterceptHandler()]
        _log.propagate = False
