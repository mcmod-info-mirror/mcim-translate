from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime
import time

from translate_mod_summary.translate import translate_text, Translation, Platform, Mode
from translate_mod_summary.database import init_engine, database
from translate_mod_summary.config import Config
from translate_mod_summary.logger import log

config = Config.load()

translate_config = config.translate

CHUNK_SIZE = translate_config.chunk_size

def translate_mutil_texts(
    translations: List[Translation],
) -> tuple[List[Translation], List[Translation], int]:
    failed_jobs: List[Translation] = []
    final_failed_jobs: List[Translation] = []
    success_jobs: List[Translation] = []
    total_used_token = 0

    def process_translation(translation: Translation, mode: Mode) -> tuple[Optional[Translation], int]:
        start_time = time.time()
        translated_text, total_tokens = translate_text(translation.original_text, mode=mode)
        if translated_text:
            translation.translated_text = translated_text
            log.debug(
                f"Translated {translation.model_dump()} with {total_tokens} tokens in {round(time.time() - start_time, 2)} seconds."
            )
            return translation, total_tokens
        else:
            log.error(f"Failed to translate {translation.model_dump()} in {time.time() - start_time} seconds.")
            return None, 0

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(process_translation, translation, Mode.UPGRADE): translation for translation in translations}
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
                log.error(f"Error processing translation {translation.model_dump()}: {e}")
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


def query_modrinth_database() -> List[Translation]:
    start_time = time.time()
    # 未翻译记录的查询
    pipeline_untranslated = [
        {"$project": {"_id": 1, "description": 1}},
        {
            "$lookup": {
                "from": "modrinth_translated",
                "localField": "_id",
                "foreignField": "_id",
                "as": "modrinth_translated",
            }
        },
        {"$match": {"modrinth_translated": {"$eq": []}}},
        {"$project": {"_id": 1, "description": 1}},
        {"$limit": CHUNK_SIZE},
    ]

    collection = database.get_collection("modrinth_projects")
    result = list(collection.aggregate(pipeline_untranslated))

    if not result:
        # 当未找到未翻译的记录时，查询原文本已改变的记录
        pipeline_changed = [
            {"$project": {"_id": 1, "description": 1}},
            {
                "$lookup": {
                    "from": "modrinth_translated",
                    "let": {"project_id": "$_id", "description": "$description"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": ["$_id", "$$project_id"]},
                                        {"$ne": ["$original", "$$description"]},
                                    ]
                                }
                            }
                        }
                    ],
                    "as": "modrinth_translated",
                }
            },
            {"$match": {"modrinth_translated": {"$ne": []}}},
            {"$project": {"_id": 1, "description": 1}},
            {"$limit": CHUNK_SIZE},
        ]
        result = list(collection.aggregate(pipeline_changed))
    
    log.debug(f"Found {len(result)} records in {time.time() - start_time} seconds.")

    return [
        Translation(
            platform=Platform.MODRINTH,
            id=project["_id"],
            original_text=project["description"],
        )
        for project in result
    ]


def query_curseforge_database() -> List[Translation]:
    start_time = time.time()
    # 未翻译记录的查询
    pipeline_untranslated = [
        {"$match": {"classId": 6}},
        {"$project": {"_id": 1, "summary": 1}},
        {
            "$lookup": {
                "from": "curseforge_translated",
                "localField": "_id",
                "foreignField": "_id",
                "as": "curseforge_translated",
            }
        },
        {"$match": {"curseforge_translated": {"$eq": []}}},
        {"$limit": CHUNK_SIZE},
    ]

    collection = database.get_collection("curseforge_mods")
    result = list(collection.aggregate(pipeline_untranslated))
    if not result:
        # 当未找到未翻译的记录时，查询原文本已改变的记录
        pipeline_changed = [
            {"$match": {"classId": 6}},
            {"$project": {"_id": 1, "summary": 1}},
            {
                "$lookup": {
                    "from": "curseforge_translated",
                    "let": {"mod_id": "$_id", "summary": "$summary"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": ["$_id", "$$mod_id"]},
                                        {"$ne": ["$original", "$$summary"]},
                                    ]
                                }
                            }
                        }
                    ],
                    "as": "curseforge_translated",
                }
            },
            {"$match": {"curseforge_translated": {"$ne": []}}},
            {"$limit": CHUNK_SIZE},
        ]

        result = list(collection.aggregate(pipeline_changed))

    log.debug(f"Found {len(result)} records in {time.time() - start_time} seconds.")

    return [
        Translation(
            platform=Platform.CURSEFORGE,
            id=mod["_id"],
            original_text=mod["summary"],
        )
        for mod in result
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
                "translated_at": datetime.datetime.now(),
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
            success_results, failed_results, used_token = translate_mutil_texts(
                translate_jobs
            )
            total_used_token += used_token
            for result in success_results:
                update_database(result)
            success_count += len(success_results)
            failed_count += len(failed_results)
        else:
            break
    log.info(
        f"Totally Translated {success_count} modrinth projects, failed {failed_count}, used {total_used_token} tokens."
    )


def check_curseforge_translations():
    success_count = 0
    failed_count = 0
    total_used_token = 0
    while True:
        translate_jobs = query_curseforge_database()
        if len(translate_jobs) > 0:
            success_results, failed_results, used_token = translate_mutil_texts(
                translate_jobs
            )
            total_used_token += used_token
            for result in success_results:
                update_database(result)
            success_count += len(success_results)
            failed_count += len(failed_results)
        else:
            break
    log.info(
        f"Totally Translated {success_count} curseforge mods, failed {failed_count}, used {total_used_token} tokens."
    )


if __name__ == "__main__":
    init_engine()
    scheduler = BackgroundScheduler()

    # modrinth_translate_job = scheduler.add_job(
    #     check_modrinth_translations,
    #     trigger=IntervalTrigger(seconds=config.interval),
    #     next_run_time=datetime.datetime.now(),
    #     name="modrinth_translate_job",
    # )

    curseforge_translate_job = scheduler.add_job(
        check_curseforge_translations,
        trigger=IntervalTrigger(seconds=config.interval),
        next_run_time=datetime.datetime.now(),
        name="curseforge_translate_job",
    )

    # 启动调度器
    scheduler.start()
    log.info("Scheduler started")

    # 保持主线程运行
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        log.info("Shutting down...")
        scheduler.shutdown()
