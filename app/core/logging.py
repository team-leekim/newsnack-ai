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
        "uvicorn": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn.error": {
            "level": "INFO",
            "propagate": True,
        },
        "uvicorn.access": {
            "level": "WARNING",
            "propagate": True,
        },
    }
}

def setup_logging():
    logging.Formatter.converter = time.gmtime
    logging.config.dictConfig(LOGGING_CONFIG)
