import json
import os
from typing import Optional
from pydantic import BaseModel

CONFIG_PATH = "config.json"

class MongodbConfigModel(BaseModel):
    host: str = "mongodb"
    port: int = 27017
    auth: bool = True
    user: str = "username"
    password: str = "password"
    database: str = "database"

class Translate(BaseModel):
    api_key: str = "<api key>"
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model: str = "deepseek-v3"
    enable_backup: bool = False
    backup_model: Optional[str] = None
    backup_api_key: Optional[str] = None
    backup_base_url: Optional[str] = None
    temperature: float = 0.6
    target_language: str = "中文"
    chunk_size: int = 2
    multiprocess: bool = False
    enable_thinking: bool = False
    thinking_budget: int = 256

class Telegram(BaseModel):
    enable: bool = False
    bot_api: str = "https://api.telegram.org/bot"
    bot_token: str = "<bot token>"
    chat_id: str = "<chat id>"

# 合并配置模型，将三个配置嵌套在一起
class ConfigModel(BaseModel):
    debug: bool = False
    mongodb: MongodbConfigModel = MongodbConfigModel()
    translate: Translate = Translate()
    telegram: Telegram = Telegram()
    interval: int = 3600 * 24

class Config:
    @staticmethod
    def save(model: ConfigModel = ConfigModel(), target=CONFIG_PATH):
        with open(target, "w", encoding="UTF-8") as fd:
            json.dump(model.model_dump(), fd, indent=4)

    @staticmethod
    def load(target=CONFIG_PATH) -> ConfigModel:
        if not os.path.exists(target):
            Config.save(target=target)
            return ConfigModel()
        with open(target, "r", encoding="UTF-8") as fd:
            data = json.load(fd)
        return ConfigModel(**data)