import json
import os
from typing import Optional
from pydantic import BaseModel, ValidationError, validator

from utils.config.constants import CONFIG_PATH

# MCIM config path
TRANSLATE_CONFIG_PATH = os.path.join(CONFIG_PATH, "translate.json")

class Translate(BaseModel):
    api_key: str = "<api key>"
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model: str = "qwen-plus"
    temperature: float = 0.6
    target_language: str = "Chinese"
    chunk_size: int = 75


class TranslateConfig:
    @staticmethod
    def save(model: Translate = Translate(), target=TRANSLATE_CONFIG_PATH):
        with open(target, "w") as fd:
            json.dump(model.model_dump(), fd, indent=4)

    @staticmethod
    def load(target=TRANSLATE_CONFIG_PATH) -> Translate:
        if not os.path.exists(target):
            TranslateConfig.save(target=target)
            return Translate()
        with open(target, "r") as fd:
            data = json.load(fd)
        return Translate(**data)
