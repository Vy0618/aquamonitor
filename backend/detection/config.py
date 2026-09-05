"""Default configuration for the bottle counting pipeline.

Tune ``COUNTING_LINE`` to the camera view before using it in production.  The
coordinates assume the 640 x 480 capture configured in ``object-ident.py``.
"""

import os
from dataclasses import dataclass
from typing import Literal

Point = tuple[float, float]
Direction = Literal["any", "positive", "negative"]


@dataclass(frozen=True)
class CountingLineConfig:
    start: Point
    end: Point
    direction: Direction = "any"
    classes_to_count: frozenset[str] | None = frozenset({"bottle"})
    max_missing_frames: int = 90


@dataclass(frozen=True)
class ByteTrackConfig:
    track_activation_threshold: float = 0.25
    lost_track_buffer: int = 30
    minimum_matching_threshold: float = 0.8
    frame_rate: int = 30
    minimum_consecutive_frames: int = 1


@dataclass(frozen=True)
class ApiConfig:
    """Destination for aggregate counts (implemented by the Phase 3 API)."""

    base_url: str = os.getenv("BOTTLE_COUNT_API_URL", "http://127.0.0.1:8000")
    station_id: int = int(os.getenv("BOTTLE_COUNT_STATION_ID", "1"))
    publish_interval_seconds: float = float(
        os.getenv("BOTTLE_COUNT_PUBLISH_INTERVAL", "5")
    )
    # Phase 3 adds the receiving endpoint. Keep local camera testing quiet until
    # then; set BOTTLE_COUNT_API_ENABLED=1 to enable publishing.
    enabled: bool = os.getenv("BOTTLE_COUNT_API_ENABLED", "0") == "1"


# Horizontal line through the middle of the current 640 x 480 camera frame.
# This is deliberately centralized so a later UI/config file can replace it.
COUNTING_LINE = CountingLineConfig(start=(0, 240), end=(640, 240))
BYTETRACK = ByteTrackConfig()
API = ApiConfig()
