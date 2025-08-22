from typing import List, Tuple
import time

from translate_mod_summary.translate import Translation
from translate_mod_summary.constants import Platform
from translate_mod_summary.database.mongodb import database
from translate_mod_summary.config import Config
from translate_mod_summary.logger import log

config = Config.load()

translate_config = config.translate


def query_curseforge_database(
    start_at: int, batch_size: int
) -> Tuple[int, List[Translation]]:
    start_time = time.time()

    results: List[Translation] = []

    while len(results) < batch_size:
        curseforge_collection = database.get_collection("curseforge_mods")
        translated_curseforge_collection = database.get_collection("curseforge_translated")
        origin_query_results = list(
            curseforge_collection.find(
                {"gameId": 432, "summary": {"$exists": True, "$ne": ""}},
                {"_id": 1, "summary": 1},
            )
            .sort({"_id": 1})
            .skip(start_at)
            .limit(batch_size)
        )

        if len(origin_query_results) == 0:
            break

        translated_query_results = list(
            translated_curseforge_collection.find(
                {"_id": {"$in": [mod["_id"] for mod in origin_query_results]}},
                {"_id": 1, "original": 1},
            )
            .sort({"_id": 1})
        )

        for mod in origin_query_results:
            translated_mod = next(
                (t for t in translated_query_results if t["_id"] == mod["_id"]), None
            )
            if not translated_mod or translated_mod["original"] != mod["summary"]:
                results.append(                    Translation(
                        platform=Platform.CURSEFORGE,
                        id=mod["_id"],
                        original_text=mod["summary"],
                        translated_text=translated_mod["translated"] if translated_mod else None
                    )
                )
        start_at += batch_size

    log.debug(f"Found {len(results)} records in {round(time.time() - start_time, 2)} seconds.")

    return start_at, results
