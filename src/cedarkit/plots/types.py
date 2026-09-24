from dataclasses import dataclass
from typing import Tuple


@dataclass
class AreaRange:
    start_longitude: float
    end_longitude: float
    start_latitude: float
    end_latitude: float

    def to_tuple(self) -> Tuple[float, float, float, float]:
        return self.start_longitude, self.end_longitude, self.start_latitude, self.end_latitude

    @classmethod
    def from_tuple(cls, area: Tuple[float, float, float, float]) -> 'AreaRange':
        return cls(area[0], area[1], area[2], area[3])
