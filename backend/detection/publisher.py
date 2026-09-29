"""One HTTP worker; scheduling never performs network I/O on the caller."""

import logging
import threading

from .api_client import BottleCountApiClient

LOGGER = logging.getLogger(__name__)


class BackgroundPublisher:
    def __init__(self, client: BottleCountApiClient) -> None:
        self.client = client
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread = None
        if client.config.enabled:
            self._thread = threading.Thread(target=self._run, name="detection-publisher", daemon=True)
            self._thread.start()

    def request(self) -> bool:
        """Coalesce requests; True means scheduled, not delivered."""
        if self._thread is None or self._stop.is_set():
            return False
        self._wake.set()
        return True

    def _run(self) -> None:
        while True:
            self._wake.wait()
            self._wake.clear()
            try:
                self.client.publish()
            except Exception:
                LOGGER.exception("Unexpected error publishing detection events")
            if self._stop.is_set():
                return

    def close(self, timeout: float = 5.0) -> bool:
        """Request a final attempt and wait at most timeout seconds."""
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout)
            if self._thread.is_alive():
                LOGGER.warning("Publisher shutdown timed out; delivery is not confirmed")
                return False
        pending = self.client.pending_count
        if pending:
            LOGGER.warning("Closing with %s unsent events in memory", pending)
        return pending == 0
