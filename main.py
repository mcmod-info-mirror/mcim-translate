from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from typing import List, Optional
from loguru import logger
import datetime
import time

from translate_mod_summary.translate import translate_text, Translation, Platform, Mode
from translate_mod_summary.database import init_engine, database
from translate_mod_summary.config import Config


config = Config.load()

translate_config = config.translate

CHUNK_SIZE = translate_config.chunk_size


def translate_mutil_texts(translations: List[Translation]) -> tuple[List[Translation], int]:
    failed_jobs: List[Translation] = []
    final_failed_jobs: List[Translation] = []
    success_job: List[Translation] = []
    total_used_token = 0
    for translation in translations:
        translated_text, total_tokens = translate_text(
            translation.original_text, mode=Mode.UPGRADE
        )
        if translated_text:
            translation.translated_text = translated_text
            success_job.append(translation)
            total_used_token += total_tokens
            logger.debug(
                f"Translated {translation.model_dump()} with {total_tokens} tokens."
            )
        else:
            if translate_config.enbale_backup:
                failed_jobs.append(translation)
            logger.error(f"Failed to translate {translation.model_dump()}")

    logger.info(f"Translated {len(translations)} texts, failed {len(failed_jobs)}")

    if len(failed_jobs) > 0 and translate_config.enbale_backup:
        for translation in failed_jobs:
            translated_text, total_tokens = translate_text(
                translation.original_text, mode=Mode.DOWNGRADE
            )
            if translated_text:
                translation.translated_text = translated_text
                total_used_token += total_tokens
                success_job.append(translation)
                logger.debug(
                    f"Translated {translation.model_dump()} with downgrade model, used {total_tokens} tokens."
                )
            else:
                final_failed_jobs.append(translation)
                logger.error(
                    f"Failed to translate {translation.model_dump()} with downgrade model."
                )
    else:
        final_failed_jobs = failed_jobs

    return success_job, final_failed_jobs, total_used_token


def query_modrinth_database(skip: Optional[int] = 0) -> List[Translation]:
    # 从 modrinth_projects 中查询所有 _id 不存在于 translated_summary 中的记录
    result = database.get_collection("modrinth_projects").aggregate([
        {
            "$lookup": {
                "from": "modrinth_translated",
                "localField": "_id",
                "foreignField": "_id",
                "as": "modrinth_translated"
            }
        },
        {
            "$match": {
                "modrinth_translated": {"$size": 0}
            }
        },
        {
            "$project": {
                "_id": 1,
                "description": 1
            }
        },
        {
            "$skip": skip
        },
        {
            "$limit": CHUNK_SIZE
        }
    ])

    return [
        Translation(
            platform=Platform.MODRINTH,
            id=project["_id"],
            original_text=project["description"],
        )
        for project in result
    ]


def query_curseforge_database(skip: Optional[int] = 0) -> List[Translation]:
    # 从 curseforge_mods 中查询所有 _id 不存在于 translated_summary 中的记录
    result = database.get_collection("curseforge_mods").aggregate([
        {
            "$lookup": {
                "from": "curseforge_translated",
                "localField": "_id",
                "foreignField": "_id",
                "as": "curseforge_translated"
            }
        },
        {
            "$match": {
                "curseforge_translated": {"$size": 0}
            }
        },
        {
            "$project": {
                "_id": 1,
                "summary": 1
            }
        },
        {
            "$limit": CHUNK_SIZE
        }
    ])

    return [
        Translation(
            platform=Platform.CURSEFORGE,
            id=project["_id"],
            original_text=project["summary"],
        )
        for project in result
    ]


def update_database(translation: Translation):
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
                "translated_at": datetime.datetime.now()
            }
        },
        upsert=True,
    )


def check_modrinth_translations():
    success_count = 0
    failed_count = 0
    total_used_token = 0
    while True:
        translate_jobs = query_modrinth_database()
        if len(translate_jobs) > 0:
            success_results, failed_results, used_token = translate_mutil_texts(translate_jobs)
            total_used_token += used_token
            for result in success_results:
                update_database(result)
            success_count += len(success_results)
            failed_count += len(failed_results)
        else:
            break
    logger.info(
        f"Totally Translated {success_count} modrinth projects, failed {failed_count}, used {total_used_token} tokens."
    )


def check_curseforge_translations():
    success_count = 0
    failed_count = 0
    total_used_token = 0
    while True:
        translate_jobs = query_curseforge_database()
        if len(translate_jobs) > 0:
            success_results, failed_results, used_token  = translate_mutil_texts(translate_jobs)
            total_used_token += used_token
            for result in success_results:
                update_database(result)
            success_count += len(success_results)
            failed_count += len(failed_results)
        else:
            break
    logger.info(
        f"Totally Translated {success_count} curseforge mods, failed {failed_count}, used {total_used_token} tokens."
    )


if __name__ == "__main__":
    init_engine()
    scheduler = BackgroundScheduler()

    modrinth_translate_job = scheduler.add_job(
        check_modrinth_translations,
        trigger=IntervalTrigger(seconds=config.interval),
        next_run_time=datetime.datetime.now(),
    )

    curseforge_translate_job = scheduler.add_job(
        check_curseforge_translations,
        trigger=IntervalTrigger(seconds=config.interval),
        next_run_time=datetime.datetime.now(),
    )

    # 启动调度器
    scheduler.start()
    logger.info("Scheduler started, waiting for 10s.")

    # 保持主线程运行
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")
        scheduler.shutdown()
