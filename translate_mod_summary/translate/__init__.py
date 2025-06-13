from openai import OpenAI
from pydantic import BaseModel
from typing import List, Union, Optional

from translate_mod_summary.logger import log
from translate_mod_summary.config import Config
from translate_mod_summary.constants import Platform, Mode
import re


translate_config = Config.load().translate

CLIENT = OpenAI(api_key=translate_config.api_key, base_url=translate_config.base_url)
if translate_config.enbale_backup:
    BACKUP_CLIENT = OpenAI(
        api_key=translate_config.backup_api_key,
        base_url=translate_config.backup_base_url,
    )

CHUNK_SIZE = translate_config.chunk_size


class Translation(BaseModel):
    platform: Platform
    id: Union[int, str]
    original_text: str
    translated_text: Optional[str] = None
    mode: Mode = Mode.UPGRADE


def post_processing_text(translated_text: str) -> str:
    """
    后处理译文

    - 去掉首尾空格
    - 去掉首尾 \n
    - 为中英文之间添加空格
    - 替换关键字
    """
    translated_text = translated_text.strip()
    translated_text = translated_text.strip("\n")

    # 替换特定关键字
    tables = {
        "我的世界": "Minecraft",
    }
    for key, value in tables.items():
        translated_text = translated_text.replace(key, value)

    # 为中英文词语之间添加空格
    translated_text = re.sub(
        r"([a-zA-Z0-9])([\u4e00-\u9fa5])", r"\1 \2", translated_text
    )
    translated_text = re.sub(
        r"([\u4e00-\u9fa5])([a-zA-Z0-9])", r"\1 \2", translated_text
    )

    # 添加更多替换规则
    return translated_text


def translate_text(
    text,
    target_language: str = translate_config.target_language,
    mode: Mode = Mode.UPGRADE,
) -> tuple[Optional[str], int]:
    try:
        message = [
            {
                "role": "system",
                # "content": f"你是专业的 Minecraft 中文翻译助手，接地气地直接地将文本翻译为{target_language}给我，文本背景是 Minecraft Mod 介绍，特有名词不要翻译",
                "content": f"Translate the introduction text of a Minecraft Mod into {target_language}. Do not translate mod-specific terms. Translate vanilla Minecraft item names according to the {target_language} Minecraft Wiki. No explanations, no additional notes, only the translated text.",
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
            translated_text = post_processing_text(translated_text)
            return translated_text, usage.total_tokens
        else:
            raise Exception("Failed to get response from API")
    except Exception as e:
        log.error(e)
        return None, 0
