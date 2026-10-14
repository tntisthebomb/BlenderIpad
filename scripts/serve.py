#!/usr/bin/env python3
"""Local development only. Deploy web/ over HTTPS to use the PWA on an iPad."""
import argparse
import ssl
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map,
                      ".wasm": "application/wasm", ".js": "text/javascript",
                      ".webmanifest": "application/manifest+json"}

    def end_headers(self):
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--directory", type=Path, default=ROOT / "web",
                        help="Directory to serve, including an extracted editor build")
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--cert", type=Path, help="Trusted HTTPS certificate")
    parser.add_argument("--key", type=Path, help="HTTPS private key")
    args = parser.parse_args()
    if bool(args.cert) != bool(args.key):
        parser.error("HTTPS requires both --cert and --key")
    if not args.directory.is_dir():
        parser.error("The directory to serve does not exist")
    server = ThreadingHTTPServer((args.bind, args.port), partial(Handler, directory=str(args.directory.resolve())))
    if args.cert:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(args.cert, args.key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
    scheme = "https" if args.cert else "http"
    print(f"Serving {args.directory} at {scheme}://{args.bind}:{server.server_port}. iPad installation requires a trusted secure origin.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
