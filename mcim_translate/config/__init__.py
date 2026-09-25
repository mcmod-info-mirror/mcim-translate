import json
import os
from typing import Any, Optional
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
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-flash"
    enable_backup: bool = False
    backup_model: Optional[str] = None
    backup_api_key: Optional[str] = None
    backup_base_url: Optional[str] = None
    temperature: float = 0.6
    target_language: str = "中文"
    chunk_size: int = 2
    multiprocess: bool = False
    # enable_thinking: bool = False
    # thinking_budget: int = 256
    extra_body: Optional[dict] = None
    reasoning_effort: Optional[str] = "low"  # "low", "medium", "high", "xhigh"

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
    curseforge_cron: str = "0 0 * * *"
    modrinth_cron: str = "0 0 * * *"

class Config:
    @staticmethod
    def save(model: ConfigModel = ConfigModel(), target=CONFIG_PATH):
        with open(target, "w", encoding="UTF-8") as fd:
            json.dump(model.model_dump(), fd, indent=4)

    @staticmethod
    def load(target=CONFIG_PATH) -> ConfigModel:
        data: dict[str, Any] = {}
        if os.path.exists(target):
            with open(target, "r", encoding="UTF-8") as fd:
                data = json.load(fd)

        values = ConfigModel().model_dump()
        Config._apply_environment(values)
        Config._merge(values, data)
        return ConfigModel.model_validate(values)

    @staticmethod
    def _merge(values: dict[str, Any], overrides: dict[str, Any]) -> None:
        for key, value in overrides.items():
            if isinstance(value, dict) and isinstance(values.get(key), dict):
                Config._merge(values[key], value)
            else:
                values[key] = value

    @staticmethod
    def _apply_environment(values: dict[str, Any], prefix: str = "") -> None:
        for key, value in values.items():
            env_name = f"{prefix}_{key}".upper() if prefix else key.upper()
            if isinstance(value, dict):
                Config._apply_environment(value, env_name)
                continue

            raw_value = os.getenv(env_name)
            if raw_value is not None:
                values[key] = Config._parse_environment_value(raw_value, value)

    @staticmethod
    def _parse_environment_value(raw_value: str, current_value: Any) -> Any:
        if raw_value == "" and current_value is None:
            return None
        if isinstance(current_value, bool):
            return raw_value.lower() in {"1", "true", "yes", "on"}
        if isinstance(current_value, int) and not isinstance(current_value, bool):
            return int(raw_value)
        if isinstance(current_value, float):
            return float(raw_value)
        if isinstance(current_value, (dict, list)) or current_value is None:
            try:
                return json.loads(raw_value)
            except json.JSONDecodeError:
                return raw_value
        return raw_value
