import sys
import logging
from uvicorn.logging import DefaultFormatter

def setup_logging():
    formatter = DefaultFormatter(
        fmt="%(levelprefix)s %(asctime)s - %(name)s - %(message)s",
        datefmt="%H:%M:%S",
        use_colors=True
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    logging.basicConfig(level=logging.INFO, handlers=[handler])

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
