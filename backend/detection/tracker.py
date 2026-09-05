"""Detector-independent adapter around Supervision's ByteTrack implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .config import BYTETRACK, ByteTrackConfig
from .line_counter import TrackedObject


@dataclass(frozen=True)
class Detection:
    """One detector result in the common xyxy format."""

    xyxy: tuple[float, float, float, float]
    confidence: float
    class_id: int = -1
    class_name: str | None = None


class ByteTrackTracker:
    """Assign stable IDs to detector outputs using ByteTrack.

    The import is intentionally deferred: geometry and counting can be tested
    or used on a development machine without tracking dependencies installed.
    """

    def __init__(self, config: ByteTrackConfig | None = None) -> None:
        try:
            import numpy as np
            import supervision as sv
        except ImportError as exc:
            raise RuntimeError(
                "ByteTrack requires 'numpy' and 'supervision'. Install requirements.txt."
            ) from exc
        config = config or BYTETRACK
        self._np = np
        self._sv = sv
        self._tracker = sv.ByteTrack(
            track_activation_threshold=config.track_activation_threshold,
            lost_track_buffer=config.lost_track_buffer,
            minimum_matching_threshold=config.minimum_matching_threshold,
            frame_rate=config.frame_rate,
            minimum_consecutive_frames=config.minimum_consecutive_frames,
        )

    def update(self, detections: Iterable[Detection]) -> list[TrackedObject]:
        """Track a frame of arbitrary detector results."""
        values = list(detections)
        xyxy = self._np.asarray([item.xyxy for item in values], dtype=float).reshape((-1, 4))
        confidence = self._np.asarray([item.confidence for item in values], dtype=float)
        class_id = self._np.asarray([item.class_id for item in values], dtype=int)
        tracked = self._tracker.update_with_detections(
            self._sv.Detections(xyxy=xyxy, confidence=confidence, class_id=class_id)
        )
        names = {item.class_id: item.class_name for item in values}
        return [
            TrackedObject(
                track_id=int(track_id),
                xyxy=tuple(map(float, box)),
                class_name=names.get(int(class_id)),
            )
            for box, class_id, track_id in zip(tracked.xyxy, tracked.class_id, tracked.tracker_id)
            if track_id is not None
        ]
