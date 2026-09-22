"""Configurações centralizadas para uma webcam USB genérica."""

from dataclasses import dataclass
import platform
from typing import Optional, Tuple

import cv2


@dataclass(frozen=True)
class WebcamConfig:
    """Altere estes valores para adequar a captura à câmera instalada."""

    device_index: int = 0
    width: int = 1280
    height: int = 720
    fps: int = 30
    # Um backend explícito tem prioridade sobre a seleção automática.
    backend: Optional[int] = None

    @property
    def resolution(self) -> Tuple[int, int]:
        return self.width, self.height

    def open_camera(self) -> cv2.VideoCapture:
        """Abre a câmera com V4L2 no Linux e pede resolução e FPS ao driver."""
        if self.backend is not None:
            camera = cv2.VideoCapture(self.device_index, self.backend)
        elif platform.system() == "Linux":
            camera = cv2.VideoCapture(self.device_index, cv2.CAP_V4L2)
        else:
            camera = cv2.VideoCapture(self.device_index)

        if not camera.isOpened():
            raise RuntimeError(
                f"Não foi possível abrir a webcam no índice {self.device_index}. "
                "Verifique a conexão ou altere device_index em webcam_config.py."
            )

        camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        camera.set(cv2.CAP_PROP_FPS, self.fps)
        return camera
