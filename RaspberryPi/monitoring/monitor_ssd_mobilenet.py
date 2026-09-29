"""Monitor SSD MobileNet; usa o mesmo fluxo de captura e contagem do YOLO."""

from RaspberryPi.monitoring.monitor_residuos import main


if __name__ == "__main__":
    main(default_detector="ssd")
