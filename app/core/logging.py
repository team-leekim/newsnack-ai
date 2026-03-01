import logging

def setup_logging():
    logging.basicConfig(
        level=logging.INFO, 
        format='%(levelname)s: %(asctime)s - %(name)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
