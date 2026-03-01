import logging

UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")

def setup_logging():
    logging.basicConfig(
        level=logging.INFO, 
        format='%(levelname)s: %(asctime)s - %(name)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    for logger_name in UVICORN_LOGGERS:
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
