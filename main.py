from apscheduler.schedulers.background import BackgroundScheduler
from pymongo import UpdateOne
from typing import List
from loguru import logger

from utils.translate import translate_mutil_texts, Translation, Platform
from utils.database import init_engine, database
from utils.config import CornConfig


def query_database() -> List[Translation]:
    mr_result = database.get_collection("modrinth_projects").find(
        {"description": {"$ne": None}, "translated_description": None}
    )
    cf_result = database.get_collection("curseforge_mods").find(
        {"summary": {"$ne": None}, "translated_summary": None}
    )
    result = [
        Translation(platform=Platform.MODRINTH, id=project["_id"], original_text=project["description"])
        for project in mr_result
    ] + [
        Translation(platform=Platform.CURSEFORGE, id=project["_id"], original_text=project["summary"])
        for project in cf_result
    ]
    logger.debug(f"Found {len(result)} items to translate.")
    return result


def update_database(translations: List[Translation]):
    mr_collection = database.get_collection("modrinth_projects")
    cf_collection = database.get_collection("curseforge_mods")
    mr_result: List[Translation] = []
    cf_result: List[Translation] = []
    for translation in translations:
        if translation.platform == Platform.MODRINTH:
            mr_result.append(translation)
        else:
            cf_result.append(translation)
    mr_collection.bulk_write(
        [
            UpdateOne(
                {"_id": translation.id},
                {"$set": {"translated_description": translation.translated_text}},
            )
            for translation in mr_result
        ]
    )
    cf_collection.bulk_write(
        [
            UpdateOne(
                {"_id": translation.id},
                {"$set": {"translated_summary": translation.translated_text}},
            )
            for translation in cf_result
        ]
    )
    logger.info(
        f"Updated {len(mr_result)} modrinth projects and {len(cf_result)} curseforge mods."
    )


def check_translations():
    translations = query_database()
    if translations:
        translations = translate_mutil_texts(translations)
        update_database(translations)
    logger.info(f"下次执行时间: {translate_job.next_run_time}")


if __name__ == "__main__":
    corn_config = CornConfig.load()
    scheduler = BackgroundScheduler()
    translate_job = scheduler.add_job(
        check_translations,
        "cron",
        day=corn_config.day,
        hour=corn_config.hour,
        minute=corn_config.minute,
        second=corn_config.second,
        timezone="Asia/Shanghai",
    )

    # 启动调度器
    scheduler.start()
    logger.info("Scheduler started.")
    logger.info(f"下次执行时间: {translate_job.next_run_time}")
    
    # 保持主线程运行
    try:
        while True:
            pass
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")
        scheduler.shutdown()
