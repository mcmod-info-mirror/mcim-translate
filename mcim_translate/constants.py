
from enum import Enum

class Platform(Enum):
    CURSEFORGE: str = "Curseforge"
    MODRINTH: str = "Modrinth"


class Mode(Enum):
    DOWNGRADE: str = "downgrade"
    UPGRADE: str = "upgrade"