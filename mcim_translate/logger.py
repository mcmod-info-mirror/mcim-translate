from loguru import logger
import sys

from mcim_translate.config import Config

config = Config.load()

class Logger:
    def __init__(self):
        self.logger = logger
        self.logger.remove()
        self.logger.add(
            sys.stdout,
            backtrace=False,
            diagnose=False,
            serialize=True,
        )

    def get_logger(self):
        return self.logger


Loggers = Logger()
log = Loggers.get_logger()
