import json
import os
from pydantic import BaseModel, ValidationError, validator

from .constants import CONFIG_PATH

# CORN config path
CORN_CONFIG_PATH = os.path.join(CONFIG_PATH, "corn.json")


class CornConfigModel(BaseModel):
    day: int = None
    hour: int = None
    minute: int = None
    second: int = None


class CornConfig:
    @staticmethod
    def save(
        model: CornConfigModel = CornConfigModel(), target=CORN_CONFIG_PATH
    ):
        with open(target, "w") as fd:
            json.dump(model.model_dump(), fd, indent=4)

    @staticmethod
    def load(target=CORN_CONFIG_PATH) -> CornConfigModel:
        if not os.path.exists(target):
            CornConfig.save(target=target)
            return CornConfigModel()
        with open(target, "r") as fd:
            data = json.load(fd)
        return CornConfigModel(**data)