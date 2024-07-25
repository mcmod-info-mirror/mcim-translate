from openai import OpenAI
from pydantic import BaseModel
from typing import List, Union, Optional
from enum import Enum
import

from utils.config import TranslateConfig
from loguru import logger

translate_config = TranslateConfig.load()

CLIENT = OpenAI(
    api_key=translate_config.api_key, base_url=translate_config.base_url
)

BACKUP_CLIENT = OpenAI(
    api_key=translate_config.backup_api_key, base_url=translate_config.backup_base_url
)

CHUNK_SIZE = translate_config.chunk_size


class Platform(Enum):
    CURSEFORGE: str = "Curseforge"
    MODRINTH: str = "Modrinth"

class Mode(Enum):
    DOWNGRADE: str = "downgrade"
    MAIN: str = "main"

class Translation(BaseModel):
    platform: Platform
    id: Union[int, str]
    original_text: str
    translated_text: Optional[str] = None
    mode: Mode = Mode.MAIN


def translate_text(text, target_language="Simplified Chinese", mode: Mode=Mode.MAIN) -> str:
    try:
        if mode == Mode.DOWNGRADE:
            response = BACKUP_CLIENT.chat.completions.create(
                model=translate_config.backup_model,
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a Minecraft mod localization assistant. Translate directly into {target_language} and return, no need for original text, other prefaces and formatting",
                    },
                    {"role": "user", "content": text},
                ],
                temperature=translate_config.temperature,
            )
        else:
            response = CLIENT.chat.completions.create(
                model=translate_config.model,
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a Minecraft mod localization assistant. Translate directly into {target_language} and return, no need for original text, other prefaces and formatting",
                    },
                    {"role": "user", "content": text},
                ],
                temperature=translate_config.temperature,
            )
        if response:
            translated_text = response.choices[0].message.content
            usage = response.usage
            return translated_text, usage.total_tokens
    except Exception as e:
        logger.error(e)
        return None, 0


def translate_chunk(
    objs: List[Translation], target_language="Simplified Chinese", mode: Mode=Mode.MAIN
) -> List[Translation]:
    texts = [obj.original_text for obj in objs]
    raw_text = "\n\n".join(texts)
    translated_text, tokens_used = translate_text(raw_text, target_language, mode)
    if translated_text:
        translated_texts = translated_text.split("\n\n")
        translated_objs = []
        for obj, translated_text in zip(objs, translated_texts):
            obj.translated_text = translated_text
            translated_objs.append(obj)
        return translated_objs, tokens_used
    else:
        logger.error("Failed to translate chunk")
        logger.debug([f"{obj.model_dump_json()}\n" for obj in objs])
        return None, tokens_used


def translate_mutil_texts(
    objs: List[Translation], target_language="Simplified Chinese", chunk_size=CHUNK_SIZE, mode: Mode=Mode.MAIN
):
    failed_objs: List[Translation] = []
    result = []
    total_tokens = 0
    chunks = [
        objs[start : start + chunk_size] for start in range(0, len(objs), chunk_size)
    ]
    logger.debug(f"Split {len(objs)} texts into {len(chunks)} chunks")
    for chunk in chunks:
        translated_objs, tokens_used = translate_chunk(chunk, target_language, mode)
        total_tokens += tokens_used
        if translated_objs:
            result.extend(translated_objs)
            logger.debug(
                f"Translated {len(translated_objs)} texts, used tokens: {tokens_used}, total tokens used: {total_tokens}"
            )
        else:
            logger.debug(f"Failed to translate chunk, used tokens: {tokens_used}")
            logger.debug(f"Switching to backup model")
            failed_objs.extend(chunk)
    if failed_objs:
        chunks = [
            failed_objs[start : start + chunk_size] for start in range(0, len(failed_objs), chunk_size)
        ]
        logger.debug(f"Split {len(failed_objs)} texts into {len(chunks)} chunks")
        for chunk in chunks:
            translated_objs, tokens_used = translate_chunk(chunk, target_language, Mode.DOWNGRADE)
            total_tokens += tokens_used
            if translated_objs:
                result.extend(translated_objs)
                logger.debug(f'Translated {len(translated_objs)} texts with backup model, used tokens: {tokens_used}, total tokens used: {total_tokens}')
            else:
                logger.debug(f"Failed to translate chunk with backup model, used tokens: {tokens_used}")
    if failed_objs:
        logger.error(f"Failed to translate {len(failed_objs)} texts")
        logger.debug([f"{obj.model_dump_json()}\n" for obj in failed_objs])
    logger.debug(f"Total tokens used: {total_tokens}")
    return result