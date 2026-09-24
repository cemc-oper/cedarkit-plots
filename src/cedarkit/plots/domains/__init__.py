"""Value objects describing geographic domains and their defaults."""

from .domain import Domain
from .east_asia_config import (
    EAST_ASIA_DOMAIN,
    SOUTH_CHINA_SEA_DOMAIN,
)
from .ens_cn_config import ENS_CN_DOMAIN
from .remaining_config import (
    CN_AREA_DOMAIN,
    EUROPE_ASIA_AREA,
    EUROPE_ASIA_DOMAIN,
    GLOBAL_AREA,
    GLOBAL_DOMAIN,
    NORTH_POLAR_AREA,
    NORTH_POLAR_DOMAIN,
)

__all__ = [
    "CN_AREA_DOMAIN",
    "Domain",
    "EAST_ASIA_DOMAIN",
    "ENS_CN_DOMAIN",
    "EUROPE_ASIA_AREA",
    "EUROPE_ASIA_DOMAIN",
    "GLOBAL_AREA",
    "GLOBAL_DOMAIN",
    "NORTH_POLAR_AREA",
    "NORTH_POLAR_DOMAIN",
    "SOUTH_CHINA_SEA_DOMAIN",
]
