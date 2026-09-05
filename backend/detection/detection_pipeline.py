"""Orchestrate detector results, ByteTrack, line counting, and publishing."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Iterable

from .api_client import BottleCountApiClient
from .config import API, COUNTING_LINE, ApiConfig, CountingLineConfig
from .line_counter import CrossingEvent, LineCounter, TrackedObject
from .tracker import ByteTrackTracker, Detection


@dataclass(frozen=True)
class PipelineResult:
    tracks: list[TrackedObject]
    crossing_events: list[CrossingEvent]
    total_count: int


class DetectionPipeline:
    """The reusable bridge between any detector and the project infrastructure."""

    def __init__(
        self,
        *,
        line_config: CountingLineConfig = COUNTING_LINE,
        api_config: ApiConfig = API,
        tracker: ByteTrackTracker | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.tracker = tracker or ByteTrackTracker()
        self.counter = LineCounter(
            (line_config.start, line_config.end),
            direction=line_config.direction,
            classes_to_count=line_config.classes_to_count,
            max_missing_frames=line_config.max_missing_frames,
        )
        self.api_client = BottleCountApiClient(api_config)
        self._publish_interval = api_config.publish_interval_seconds
        self._clock = clock
        self._last_publish_at = clock()

    def process(self, detections: Iterable[Detection]) -> PipelineResult:
        """Track one detector frame, count crossings, and publish periodically."""
        tracks = self.tracker.update(detections)
        events = self.counter.update(tracks)
        self.publish_if_due()
        return PipelineResult(tracks, events, self.counter.count)

    def publish_if_due(self, *, force: bool = False) -> bool:
        """Publish aggregates at the configured interval, or immediately if forced."""
        now = self._clock()
        if not force and now - self._last_publish_at < self._publish_interval:
            return False
        published = self.api_client.publish(self.counter.count, self.counter.count_by_direction)
        # Advance the schedule even after a network error to avoid log/request
        # storms when the Phase 3 service is unavailable.
        self._last_publish_at = now
        return published
