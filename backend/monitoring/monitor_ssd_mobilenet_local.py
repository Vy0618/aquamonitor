"""Entrada mantida por compatibilidade; publica normalmente no backend."""

from backend.monitoring.monitor_residuos import main


if __name__ == "__main__":
    main(default_detector="ssd")
