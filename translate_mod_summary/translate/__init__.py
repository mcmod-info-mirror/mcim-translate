from openai import OpenAI
from pydantic import BaseModel
from typing import List, Union, Optional
from translate_mod_summary.logger import log

from translate_mod_summary.config import Config
from translate_mod_summary.constants import Platform, Mode


translate_config = Config.load().translate

CLIENT = OpenAI(api_key=translate_config.api_key, base_url=translate_config.base_url)
if translate_config.enbale_backup:
    BACKUP_CLIENT = OpenAI(
        api_key=translate_config.backup_api_key, base_url=translate_config.backup_base_url
    )

CHUNK_SIZE = translate_config.chunk_size


class Translation(BaseModel):
    platform: Platform
    id: Union[int, str]
    original_text: str
    translated_text: Optional[str] = None
    mode: Mode = Mode.UPGRADE


def translate_text(text, target_language: str = translate_config.target_language, mode: Mode = Mode.UPGRADE) -> tuple[Optional[str], int]:
    try:
        message = [
            {
                "role": "system",
                "content": f"你是专业的 Minecraft 中文翻译助手，接地气地直接地将文本翻译为{target_language}给我，文本背景是 Minecraft Mod 介绍，特有名词不要翻译",
            },
            {"role": "user", "content": text},
        ]
        if mode == Mode.DOWNGRADE:
            response = BACKUP_CLIENT.chat.completions.create(
                model=translate_config.backup_model,
                messages=message,
                temperature=translate_config.temperature,
            )
        else:
            response = CLIENT.chat.completions.create(
                model=translate_config.model,
                messages=message,
                temperature=translate_config.temperature,
            )
        if response:
            translated_text = response.choices[0].message.content
            usage = response.usage
            return translated_text, usage.total_tokens
    except Exception as e:
        log.error(e)
        return None, 0
