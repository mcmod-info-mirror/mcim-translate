from typing import List
import time

from mcim_translate.translate import Translation
from mcim_translate.constants import Platform
from mcim_translate.database.mongodb import database
from mcim_translate.config import Config
from mcim_translate.logger import log

config = Config.load()

translate_config = config.translate


def query_modrinth_database(batch_size: int) -> List[Translation]:
    start_time = time.time()
    results: List[Translation] = []

    translated_modrinth_collection = database.get_collection("modrinth_translated")

    for translated_mod in translated_modrinth_collection.find(
        {"need_to_update": True}, {"_id": 1, "original": 1}
    ).limit(batch_size):
        results.append(
            Translation(
                platform=Platform.MODRINTH,
                id=translated_mod["_id"],
                original_text=translated_mod["original"],
                translated_text=None,
            )
        )

    log.debug(
        f"Found {len(results)} records in {round(time.time() - start_time, 2)} seconds."
    )

    return results
