"""Default configuration for the bottle counting pipeline.

Tune ``COUNTING_LINE`` to the camera view before using it in production.  The
coordinates assume the 640 x 480 capture configured in ``object-ident.py``.
"""

from backend.settings import load_config

SETTINGS = load_config()
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
    """Destination for individual crossing events."""

    base_url: str = SETTINGS['backend']['base_url']
    station_id: int = SETTINGS['station_id']
    publish_interval_seconds: float = SETTINGS['backend']['publish_interval_seconds']
    enabled: bool = SETTINGS['backend']['enabled']
    detections_path: str = SETTINGS['backend']['detections_path']
    timeout_seconds: float = SETTINGS['backend']['timeout_seconds']


def line_config(settings, width=None, height=None):
    width = width or settings['camera']['width']
    height = height or settings['camera']['height']
    y = height * settings['tracking']['line_y_ratio']
    return CountingLineConfig(
        start=(0, y), end=(width, y),
        direction={'both': 'any', 'down': 'positive', 'up': 'negative'}[settings['tracking']['direction']],
        classes_to_count=frozenset(settings['ssd_mobilenet']['detection_types']),
        max_missing_frames=settings['tracking']['max_missing_frames'],
    )


COUNTING_LINE = line_config(SETTINGS)
BYTETRACK = ByteTrackConfig(**SETTINGS['bytetrack'])
API = ApiConfig()
