"""Aguarda a conexao PostgreSQL antes de iniciar a API pelo systemd."""

import os
import time

import psycopg


def wait_database(url, timeout=60, interval=1):
    deadline = time.monotonic() + timeout
    print(f"Aguardando PostgreSQL (ate {timeout:g} segundos)...", flush=True)
    while True:
        try:
            with psycopg.connect(url, connect_timeout=2) as connection:
                connection.execute("SELECT 1")
            print("PostgreSQL pronto.", flush=True)
            return
        except psycopg.OperationalError:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError(
                    "PostgreSQL indisponivel. Confira usuario, senha, banco e servico."
                ) from None
            time.sleep(min(interval, remaining))


def main():
    url = os.environ.get("AQUAMONITOR_DATABASE_URL")
    if not url:
        raise SystemExit("Defina AQUAMONITOR_DATABASE_URL em /etc/aquamonitor/api.env.")
    try:
        wait_database(url)
    except RuntimeError as error:
        raise SystemExit(str(error)) from None


if __name__ == "__main__":
    main()
