"""HTTP boundary for publishing aggregate bottle counts."""

from __future__ import annotations

import logging
from typing import Mapping

import requests

from .config import ApiConfig

LOGGER = logging.getLogger(__name__)


class BottleCountApiClient:
    """Publish the current aggregate; detection failures never stop the camera."""

    def __init__(self, config: ApiConfig) -> None:
        self.config = config

    def publish(self, count: int, count_by_direction: Mapping[str, int]) -> bool:
        """Send the aggregate expected by the Phase 3 bottle-count endpoint."""
        if not self.config.enabled:
            return False
        endpoint = (
            f"{self.config.base_url.rstrip('/')}/api/stations/"
            f"{self.config.station_id}/bottle-count"
        )
        payload = {
            "count": count,
            "count_by_direction": dict(count_by_direction),
        }
        try:
            response = requests.post(endpoint, json=payload, timeout=3)
            response.raise_for_status()
        except requests.RequestException as exc:
            LOGGER.warning("Could not publish bottle count to %s: %s", endpoint, exc)
            return False
        return True
