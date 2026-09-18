"""Rastreador leve por centróide e evento de cruzamento de linha."""

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from RaspberryPi.detection.yolo_detector import Detection


Point = Tuple[int, int]


@dataclass
class TrackedObject:
    track_id: int
    class_name: str
    centroid: Point
    previous_centroid: Optional[Point] = None
    missing_frames: int = 0
    counted: bool = False


@dataclass(frozen=True)
class Crossing:
    track_id: int
    class_name: str


class LineTracker:
    def __init__(
        self,
        line_y: int,
        max_distance: int = 90,
        max_missing_frames: int = 20,
        direction: str = "both",  # "down", "up" ou "both"
    ) -> None:
        if direction not in {"down", "up", "both"}:
            raise ValueError("direction deve ser 'down', 'up' ou 'both'.")
        self.line_y = line_y
        self.max_distance = max_distance
        self.max_missing_frames = max_missing_frames
        self.direction = direction
        self._next_id = 1
        self.objects: Dict[int, TrackedObject] = {}

    def update(self, detections: Iterable[Detection]) -> List[Crossing]:
        """Atualiza tracks e retorna apenas objetos que cruzaram a linha uma vez."""
        pending = list(detections)
        unmatched_tracks = set(self.objects)
        matches: List[Tuple[int, int]] = []

        # Associação gulosa: impede que objetos de classes diferentes sejam unidos.
        candidates = []
        for det_index, detection in enumerate(pending):
            for track_id, tracked in self.objects.items():
                if tracked.class_name != detection.class_name:
                    continue
                distance = self._distance(tracked.centroid, detection.centroid)
                if distance <= self.max_distance:
                    candidates.append((distance, track_id, det_index))
        used_detections = set()
        for _, track_id, det_index in sorted(candidates):
            if track_id not in unmatched_tracks or det_index in used_detections:
                continue
            matches.append((track_id, det_index))
            unmatched_tracks.remove(track_id)
            used_detections.add(det_index)

        crossings = []
        for track_id, det_index in matches:
            tracked = self.objects[track_id]
            tracked.previous_centroid = tracked.centroid
            tracked.centroid = pending[det_index].centroid
            tracked.missing_frames = 0
            if not tracked.counted and self._crossed_line(tracked):
                tracked.counted = True
                crossings.append(Crossing(track_id, tracked.class_name))

        for track_id in unmatched_tracks:
            self.objects[track_id].missing_frames += 1

        for det_index, detection in enumerate(pending):
            if det_index not in used_detections:
                self.objects[self._next_id] = TrackedObject(
                    self._next_id, detection.class_name, detection.centroid
                )
                self._next_id += 1

        self.objects = {
            track_id: tracked
            for track_id, tracked in self.objects.items()
            if tracked.missing_frames <= self.max_missing_frames
        }
        return crossings

    def _crossed_line(self, tracked: TrackedObject) -> bool:
        if tracked.previous_centroid is None:
            return False
        old_y, new_y = tracked.previous_centroid[1], tracked.centroid[1]
        went_down = old_y < self.line_y <= new_y
        went_up = old_y > self.line_y >= new_y
        return (self.direction in {"down", "both"} and went_down) or (
            self.direction in {"up", "both"} and went_up
        )

    @staticmethod
    def _distance(first: Point, second: Point) -> float:
        return ((first[0] - second[0]) ** 2 + (first[1] - second[1]) ** 2) ** 0.5
