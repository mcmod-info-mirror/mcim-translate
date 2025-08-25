from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from typing import Callable, List
import datetime
import time

from mcim_translate.translate import (
    update_translation,
    process_translation,
    process_multi_translations,
    Translation,
)
from mcim_translate.database.mongodb import init_engine
from mcim_translate.database.mongodb.query import (
    query_curseforge_database,
    query_modrinth_database,
)
from mcim_translate.config import Config
from mcim_translate.logger import log
from mcim_translate.constants import Mode, Platform
from mcim_translate.telegram import send_result


config = Config.load()

translate_config = config.translate


def check_translations(query_func: Callable[[int], List[Translation]]) -> tuple:
    success_count = 0
    failed_count = 0
    total_used_token = 0

    translated_ids = []

    while True:
        success_results = []
        failed_results = []
        translate_jobs = query_func(
            batch_size=config.translate.chunk_size
        )
        if len(translate_jobs) > 0:
            if config.translate.multiprocess:
                success_results, failed_results, used_token = (
                    process_multi_translations(translate_jobs)
                )
                total_used_token += used_token
                success_count += len(success_results)
                failed_count += len(failed_results)
            else:
                for translation in translate_jobs:
                    result, tokens = process_translation(translation, Mode.UPGRADE)
                    if result:
                        success_results.append(result)
                        total_used_token += tokens
                    else:
                        result, tokens = process_translation(
                            translation, Mode.DOWNGRADE
                        )
                        if result:
                            success_results.append(result)
                            total_used_token += tokens
                        else:
                            failed_results.append(translation)

                    total_used_token += tokens

            for result in success_results:
                update_translation(result)
                translated_ids.append(result.id)

            log.info(f"Successfully translated {len(success_results)} items.")

            success_count += len(success_results)
            failed_count += len(failed_results)
        else:
            break

    return success_count, failed_count, total_used_token, translated_ids


def check_modrinth_translations():
    log.info("Starting Modrinth translation check...")
    success_count, failed_count, total_used_token, translated_ids = check_translations(
        query_modrinth_database
    )
    log.info(
        f"Totally Translated {success_count} modrinth projects, failed {failed_count}, used {total_used_token} tokens."
    )
    if len(translated_ids) > 0:
        send_result(Platform.MODRINTH, translated_ids)
        log.info("Modrinth translation check completed.")


def check_curseforge_translations():
    log.info("Starting CurseForge translation check...")
    success_count, failed_count, total_used_token, translated_ids = check_translations(
        query_curseforge_database
    )
    log.info(
        f"Totally Translated {success_count} curseforge projects, failed {failed_count}, used {total_used_token} tokens."
    )
    if len(translated_ids) > 0:
        send_result(Platform.CURSEFORGE, translated_ids)
        log.info("CurseForge translation check completed.")

if __name__ == "__main__":
    init_engine()
    scheduler = BackgroundScheduler()

    modrinth_translate_job = scheduler.add_job(
        check_modrinth_translations,
        # trigger=IntervalTrigger(seconds=config.interval),
        trigger=CronTrigger.from_crontab(config.modrinth_cron),
        next_run_time=datetime.datetime.now(),
        name="modrinth_translate_job",
    )

    curseforge_translate_job = scheduler.add_job(
        check_curseforge_translations,
        # trigger=IntervalTrigger(seconds=config.interval),
        trigger=CronTrigger.from_crontab(config.curseforge_cron),
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
