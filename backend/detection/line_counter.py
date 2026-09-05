"""Stateful, tracker-agnostic counting of objects crossing a line."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

from .geometry import Line, Point, centroid, crosses_line, side_of_line

Direction = Literal["positive", "negative"]


@dataclass(frozen=True)
class TrackedObject:
    """Minimal tracker output consumed by :class:`LineCounter`."""

    track_id: int
    xyxy: tuple[float, float, float, float]
    class_name: str | None = None


@dataclass(frozen=True)
class CrossingEvent:
    track_id: int
    point: Point
    direction: Direction
    class_name: str | None = None


@dataclass
class _TrackState:
    point: Point
    side: int
    last_seen_frame: int


class LineCounter:
    """Count each tracked object once when it traverses a finite line.

    ``positive`` means movement from the right to the left of the oriented
    line, as defined by ``geometry.signed_distance``.  Use ``direction='any'``
    to count either direction.
    """

    def __init__(
        self,
        line: Line,
        *,
        direction: Literal["any", "positive", "negative"] = "any",
        classes_to_count: frozenset[str] | None = None,
        max_missing_frames: int = 90,
    ) -> None:
        if direction not in {"any", "positive", "negative"}:
            raise ValueError("direction must be 'any', 'positive', or 'negative'")
        if max_missing_frames < 0:
            raise ValueError("max_missing_frames must be non-negative")
        self.line = line
        self.direction = direction
        self.classes_to_count = classes_to_count
        self.max_missing_frames = max_missing_frames
        self.count = 0
        self.count_by_direction: dict[Direction, int] = {"positive": 0, "negative": 0}
        self._frame = 0
        self._states: dict[int, _TrackState] = {}
        self._counted_ids: set[int] = set()

    def update(self, tracks: Iterable[TrackedObject]) -> list[CrossingEvent]:
        """Process one frame and return the crossing events detected in it."""
        self._frame += 1
        events: list[CrossingEvent] = []
        for track in tracks:
            if self.classes_to_count is not None and track.class_name not in self.classes_to_count:
                continue
            point = centroid(track.xyxy)
            side = side_of_line(point, self.line)
            previous = self._states.get(track.track_id)
            if previous and track.track_id not in self._counted_ids:
                if crosses_line(previous.point, point, self.line):
                    movement = "positive" if previous.side < side else "negative"
                    if self.direction in {"any", movement}:
                        event = CrossingEvent(track.track_id, point, movement, track.class_name)
                        events.append(event)
                        self._counted_ids.add(track.track_id)
                        self.count += 1
                        self.count_by_direction[movement] += 1

            # Keep the latest point away from the line. This lets an object
            # touch the line in one frame and cross it in the next.
            if side != 0:
                self._states[track.track_id] = _TrackState(point, side, self._frame)
            elif previous:
                previous.last_seen_frame = self._frame
        self._expire_missing_tracks()
        return events

    def reset(self) -> None:
        """Clear counts and per-track history."""
        self.count = 0
        self.count_by_direction = {"positive": 0, "negative": 0}
        self._frame = 0
        self._states.clear()
        self._counted_ids.clear()

    def _expire_missing_tracks(self) -> None:
        expired = [
            track_id
            for track_id, state in self._states.items()
            if self._frame - state.last_seen_frame > self.max_missing_frames
        ]
        for track_id in expired:
            self._states.pop(track_id, None)
            self._counted_ids.discard(track_id)
