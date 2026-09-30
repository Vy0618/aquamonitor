"""Serve os arquivos atuais do dashboard sem cache, usando apenas Python padrão."""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class DashboardHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()

    def send_head(self):
        # Não reutiliza a cópia guardada pelo servidor estático anterior (304).
        for header in ("If-Modified-Since", "If-None-Match"):
            if header in self.headers:
                del self.headers[header]
        return super().send_head()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3000)
    args = parser.parse_args()
    directory = Path(__file__).resolve().parent / "dashboard"
    handler = partial(DashboardHandler, directory=str(directory))
    with ThreadingHTTPServer((args.bind, args.port), handler) as server:
        print(f"Dashboard sem cache: http://{args.bind}:{args.port}/", flush=True)
        print(f"Pasta: {directory}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
