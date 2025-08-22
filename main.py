from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from typing import Callable, List
import datetime
import time

from translate_mod_summary.translate import (
    update_translation,
    process_translation,
    process_multi_translations,
    Translation,
)
from translate_mod_summary.database.mongodb import init_engine
from translate_mod_summary.database.mongodb.query import (
    query_curseforge_database,
    query_modrinth_database,
)
from translate_mod_summary.config import Config
from translate_mod_summary.logger import log
from translate_mod_summary.constants import Mode


config = Config.load()

translate_config = config.translate


def check_translations(query_func: Callable[[int], List[Translation]]) -> tuple:
    success_count = 0
    failed_count = 0
    total_used_token = 0
    start_at = 0

    while True:
        success_results = []
        failed_results = []
        start_at, translate_jobs = query_func(
            batch_size=config.translate.chunk_size, start_at=start_at
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

            success_count += len(success_results)
            failed_count += len(failed_results)
        else:
            break

    return success_count, failed_count, total_used_token


def check_modrinth_translations():
    success_count, failed_count, total_used_token = check_translations(
        query_modrinth_database
    )
    log.info(
        f"Totally Translated {success_count} modrinth projects, failed {failed_count}, used {total_used_token} tokens."
    )


def check_curseforge_translations():
    success_count, failed_count, total_used_token = check_translations(
        query_curseforge_database
    )
    log.info(
        f"Totally Translated {success_count} curseforge projects, failed {failed_count}, used {total_used_token} tokens."
    )


if __name__ == "__main__":
    init_engine()
    scheduler = BackgroundScheduler()

    modrinth_translate_job = scheduler.add_job(
        check_modrinth_translations,
        trigger=IntervalTrigger(seconds=config.interval),
        next_run_time=datetime.datetime.now(),
        name="modrinth_translate_job",
    )

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
