"""Queue and publish crossing events using the detection API contract."""

from collections import deque
from datetime import datetime, timezone
import logging
from uuid import uuid4

import requests

from .config import ApiConfig
from .line_counter import CrossingEvent

LOGGER = logging.getLogger(__name__)


class BottleCountApiClient:
    def __init__(self, config: ApiConfig) -> None:
        self.config = config
        self._pending: deque[dict] = deque()

    def enqueue(self, event: CrossingEvent, confidence: float) -> None:
        if not self.config.enabled:
            return
        self._pending.append({
            'event_id': str(uuid4()),
            'station_id': self.config.station_id,
            'detection_type': event.class_name or 'bottle',
            'confidence': confidence,
            'track_id': event.track_id,
            'direction': event.direction,
            'detected_at': datetime.now(timezone.utc).isoformat(),
        })

    def publish(self) -> bool:
        """Keep failed events for retry, preserving their UUID and timestamp."""
        if not self.config.enabled or not self._pending:
            return False
        endpoint = f"{self.config.base_url.rstrip('/')}/{self.config.detections_path.lstrip('/')}"
        while self._pending:
            try:
                response = requests.post(endpoint, json=self._pending[0], timeout=self.config.timeout_seconds)
                if response.status_code != 409:
                    response.raise_for_status()
            except requests.RequestException as error:
                LOGGER.warning('Could not publish detection to %s: %s', endpoint, error)
                return False
            self._pending.popleft()
        return True
