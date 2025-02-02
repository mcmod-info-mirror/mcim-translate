from loguru import logger
import sys

from translate_mod_summary.config import Config

config = Config.load()

LOGGING_FORMAT = "<green>{time:YYYYMMDD HH:mm:ss}</green> | "  # 颜色>时间
"{process.name} | "  # 进程名
"{thread.name} | "  # 进程名
"<cyan>{module}</cyan>.<cyan>{function}</cyan> | "  # 模块名.方法名
":<cyan>{line}</cyan> | "  # 行号
"<level>{level}</level>: "  # 等级
"<level>{message}</level>"  # 日志内容


class Logger:
    def __init__(self):
        self.logger = logger
        # 清空所有设置
        self.log.remove()
        # 添加控制台输出的格式,sys.stdout为输出到屏幕;关于这些配置还需要自定义请移步官网查看相关参数说明
        self.log.add(
            sys.stdout,
            format=LOGGING_FORMAT,
            level="INFO" if not config.debug else "DEBUG",
            backtrace=False,
            diagnose=False,
            serialize=True,
        )

    def get_logger(self):
        return self.logger


Loggers = Logger()
log = Loggers.get_logger()
