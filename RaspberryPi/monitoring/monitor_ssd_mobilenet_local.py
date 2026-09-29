"""Entrada mantida por compatibilidade; publica normalmente no backend."""

from RaspberryPi.monitoring.monitor_residuos import main


if __name__ == "__main__":
    main(default_detector="ssd")
