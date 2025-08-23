from openai import OpenAI
from pydantic import BaseModel
from typing import List, Union, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import time

from translate_mod_summary.logger import log
from translate_mod_summary.config import Config
from translate_mod_summary.constants import Platform, Mode
from translate_mod_summary.database.mongodb import database
import re


translate_config = Config.load().translate

CLIENT = OpenAI(api_key=translate_config.api_key, base_url=translate_config.base_url)
if translate_config.enbale_backup:
    BACKUP_CLIENT = OpenAI(
        api_key=translate_config.backup_api_key,
        base_url=translate_config.backup_base_url,
    )
else:
    BACKUP_CLIENT = None

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
            if not BACKUP_CLIENT:
                log.warning("Backup client is not available.")
                return None, 0
            response = BACKUP_CLIENT.chat.completions.create(
                model=translate_config.backup_model,
                messages=message,
                temperature=translate_config.temperature,
                timeout=60
            )
        else:
            response = CLIENT.chat.completions.create(
                model=translate_config.model,
                messages=message,
                temperature=translate_config.temperature,
                extra_body={
                    "enable_thinking": translate_config.enable_thinking,
                    "thinking_budget": translate_config.thinking_budget,
                },
                timeout=60
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


def process_translation(
    translation: Translation, mode: Mode
) -> tuple[Optional[Translation], int]:
    start_time = time.time()
    log.debug(f"Translating {translation.model_dump()}...")
    translated_text, total_tokens = translate_text(translation.original_text, mode=mode)
    if translated_text:
        translation.translated_text = translated_text
        log.debug(
            f"Translated {translation.model_dump()} with {total_tokens} tokens in {round(time.time() - start_time, 2)} seconds."
        )
        return translation, total_tokens
    else:
        log.error(
            f"Failed to translate {translation.model_dump()} in {time.time() - start_time} seconds."
        )
        return None, 0


def process_multi_translations(
    translations: List[Translation],
) -> tuple[List[Translation], List[Translation], int]:
    failed_jobs: List[Translation] = []
    final_failed_jobs: List[Translation] = []
    success_jobs: List[Translation] = []
    total_used_token = 0

    log.info(f"Translating {len(translations)} texts with multithreading...")

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(process_translation, translation, Mode.UPGRADE): translation
            for translation in translations
        }

        for future in as_completed(futures):
            translation = futures[future]
            try:
                result, tokens = future.result()
                if result:
                    success_jobs.append(result)
                    total_used_token += tokens
                else:
                    if translate_config.enbale_backup:
                        failed_jobs.append(translation)
            except Exception as e:
                log.error(
                    f"Error processing translation {translation.model_dump()}: {e}"
                )
                if translate_config.enbale_backup:
                    failed_jobs.append(translation)

    log.info(f"Translated {len(translations)} texts, failed {len(failed_jobs)}")

    # if len(failed_jobs) > 0 and translate_config.enbale_backup:
    #     with ThreadPoolExecutor(max_workers=translate_config.max_threads) as executor:
    #         futures = {executor.submit(process_translation, translation, Mode.DOWNGRADE): translation for translation in failed_jobs}
    #         for future in as_completed(futures):
    #             translation = futures[future]
    #             try:
    #                 result, tokens = future.result()
    #                 if result:
    #                     success_jobs.append(result)
    #                     total_used_token += tokens
    #                     log.debug(
    #                         f"Translated {translation.model_dump()} with downgrade model, used {tokens} tokens."
    #                     )
    #                 else:
    #                     final_failed_jobs.append(translation)
    #                     log.error(
    #                         f"Failed to translate {translation.model_dump()} with downgrade model."
    #                     )
    #             except Exception as e:
    #                 log.error(f"Error processing translation {translation.model_dump()} with downgrade model: {e}")
    #                 final_failed_jobs.append(translation)
    # else:
    #     final_failed_jobs = failed_jobs

    return success_jobs, final_failed_jobs, total_used_token


def update_translation(translation: Translation):
    if translation.platform == Platform.MODRINTH:
        collection = database.get_collection("modrinth_translated")
    else:
        collection = database.get_collection("curseforge_translated")
    collection.update_one(
        {"_id": translation.id},
        {
            "$set": {
                "translated": translation.translated_text,
                "original": translation.original_text,
                "translated_at": datetime.now(),
            }
        },
        upsert=True,
    )
