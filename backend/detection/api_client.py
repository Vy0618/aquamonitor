"""HTTP boundary for publishing detection events."""

from __future__ import annotations

import logging
import threading
from collections import deque
from datetime import datetime, timezone
from uuid import uuid4

import requests

from .config import ApiConfig
from .line_counter import CrossingEvent

LOGGER = logging.getLogger(__name__)


class BottleCountApiClient:
    """Queue crossings and retry failures without counting an event twice."""

    def __init__(self, config: ApiConfig) -> None:
        self.config = config
        self._pending: deque[dict] = deque()
        self._queue_lock = threading.Lock()
        self._publish_lock = threading.Lock()

    @property
    def pending_count(self) -> int:
        with self._queue_lock:
            return len(self._pending)

    def enqueue(self, event: CrossingEvent, confidence: float) -> None:
        if not self.config.enabled:
            return
        payload = {
            "event_id": str(uuid4()),
            "station_id": self.config.station_id,
            "detection_type": event.class_name or "bottle",
            "confidence": confidence,
            "track_id": event.track_id,
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._queue_lock:
            self._pending.append(payload)

    def publish(self) -> bool:
        """Send a snapshot of the queue without blocking producers on HTTP."""
        with self._publish_lock:
            return self._publish_batch()

    def _publish_batch(self) -> bool:
        count = self.pending_count
        if not self.config.enabled or not count:
            return False
        endpoint = f"{self.config.base_url.rstrip('/')}/api/detections"
        for _ in range(count):
            with self._queue_lock:
                payload = self._pending[0]
            try:
                response = requests.post(endpoint, json=payload, timeout=3)
                if response.status_code != 409:
                    response.raise_for_status()
            except requests.RequestException as exc:
                LOGGER.warning("Could not publish detection to %s: %s", endpoint, exc)
                return False
            with self._queue_lock:
                self._pending.popleft()
        return True
