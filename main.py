import logging

from src import run_bot
from logger import setup_logging


logger = logging.getLogger("")

if __name__ == "__main__":
    logger.info("Starting app")
    setup_logging()
    run_bot()