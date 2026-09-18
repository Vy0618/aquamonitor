"""Detecção de resíduos usando o modelo YOLO treinado do projeto."""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import numpy as np


EXPECTED_CLASSES = ("bottle", "can", "carton", "paper", "plastic")


@dataclass(frozen=True)
class Detection:
    class_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2

    @property
    def centroid(self) -> Tuple[int, int]:
        x1, y1, x2, y2 = self.bbox
        return (x1 + x2) // 2, (y1 + y2) // 2


class YoloDetector:
    def __init__(
        self,
        model_path: str | Path = Path(__file__).resolve().parents[1] / "models" / "best (1).pt",
        confidence_threshold: float = 0.45,
        image_size: int = 640,
        device: str | None = None,
        allowed_classes: tuple[str, ...] = EXPECTED_CLASSES,
    ) -> None:
        try:
            from ultralytics import YOLO
        except ImportError as error:
            raise RuntimeError("Instale as dependências: pip install -r requirements.txt") from error

        model_file = Path(model_path)
        if not model_file.is_file():
            raise FileNotFoundError(f"Modelo YOLO não encontrado: {model_file.resolve()}")

        self.model = YOLO(str(model_file))
        self.confidence_threshold = confidence_threshold
        self.image_size = image_size
        self.device = device
        self.allowed_classes = set(allowed_classes)
        self.class_names = self._get_class_names()

    def _get_class_names(self) -> dict[int, str]:
        names = self.model.names
        return names if isinstance(names, dict) else dict(enumerate(names))

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """Executa inferência em um frame BGR e devolve somente as classes esperadas."""
        result = self.model.predict(
            source=frame,
            conf=self.confidence_threshold,
            imgsz=self.image_size,
            device=self.device,
            verbose=False,
        )[0]
        detections: List[Detection] = []

        for box in result.boxes:
            class_id = int(box.cls[0].item())
            class_name = self.class_names.get(class_id, str(class_id))
            if class_name not in self.allowed_classes:
                continue
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            detections.append(
                Detection(class_name, float(box.conf[0].item()), (x1, y1, x2, y2))
            )
        return detections
