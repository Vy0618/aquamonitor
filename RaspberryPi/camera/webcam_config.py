"""Captura USB portátil, com apenas o frame mais recente em memória."""

from dataclasses import dataclass
import platform
from threading import Condition, Event, Thread

import cv2


@dataclass(frozen=True)
class WebcamConfig:
    device_index: int = 0
    width: int = 640
    height: int = 480
    fps: int = 15
    backend: int | None = None

    def open_camera(self):
        if min(self.width, self.height, self.fps) <= 0:
            raise ValueError("Resolução e FPS devem ser positivos.")
        backend = self.backend
        if backend is None:
            backend = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_V4L2
        camera = cv2.VideoCapture(self.device_index, backend)
        if not camera.isOpened():
            camera.release()
            raise RuntimeError(f"Não foi possível abrir a webcam {self.device_index}. Verifique conexão, permissões e camera.device_index/backend no JSON.")
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        camera.set(cv2.CAP_PROP_FPS, self.fps)
        camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return camera


class LatestFrameCamera:
    """Drena a câmera durante a inferência para não acumular vídeo atrasado."""

    def __init__(self, camera):
        self.camera = camera
        self.condition = Condition()
        self.stopped = Event()
        self.frame = None
        self.sequence = 0
        self.consumed = 0
        self.error = None
        self.thread = Thread(target=self._capture, name="camera", daemon=True)
        self.thread.start()

    def _capture(self):
        try:
            while not self.stopped.is_set():
                success, frame = self.camera.read()
                if not success or frame is None or frame.size == 0:
                    raise RuntimeError("Não foi possível ler um frame da câmera.")
                with self.condition:
                    self.frame = frame
                    self.sequence += 1
                    self.condition.notify_all()
        except Exception as error:
            with self.condition:
                self.error = error
                self.condition.notify_all()

    def read(self):
        with self.condition:
            ready = self.condition.wait_for(
                lambda: self.sequence != self.consumed or self.error is not None,
                timeout=5,
            )
            if self.error is not None:
                raise RuntimeError("Falha na captura da câmera.") from self.error
            if not ready:
                raise RuntimeError("A câmera não entregou um frame em 5 segundos.")
            self.consumed = self.sequence
            return self.frame.copy()

    def close(self):
        self.stopped.set()
        self.thread.join(timeout=1)
        self.camera.release()
        self.thread.join(timeout=1)
