import logging
import logging.config
import time
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="SYSTEM")

class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get()
        return True

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {
            "()": RequestIdFilter,
        }
    },
    "formatters": {
        "default": {
            "format": "%(asctime)s.%(msecs)03dZ %(levelname)-5s %(process)d --- [%(request_id)s] %(name)-20s : %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S"
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "filters": ["request_id"],
        },
    },
    "loggers": {
        "": {
            "handlers": ["console"],
            "level": "INFO",
        },
    }
}

UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")

def setup_logging():
    logging.Formatter.converter = time.gmtime
    logging.config.dictConfig(LOGGING_CONFIG)

    for logger_name in UVICORN_LOGGERS:
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
