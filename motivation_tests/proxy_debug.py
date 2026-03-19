#!/usr/bin/env python3
"""
Transparent debug proxy between Claude Code CLI and Ollama/LM Studio.

Usage:
    python proxy_debug.py --target http://localhost:11434 --port 18434

Then set ANTHROPIC_BASE_URL=http://localhost:18434 so Claude Code
routes through this proxy.  Every request and response is logged to
proxy_debug.log (and optionally to stdout with --verbose).
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

log = logging.getLogger("proxy_debug")

TARGET_URL = "http://localhost:11434"
LOG_FILE = Path("proxy_debug.log")

# export ANTHROPIC_BASE_URL=http://localhost:11434
# export ANTHROPIC_API_KEY=ollama                                                                                             
# export ANTHROPIC_AUTH_TOKEN=ollama                              
# claude --model qwen3.5:9b   


class ProxyHandler(BaseHTTPRequestHandler):
    """Forward every request to TARGET_URL, logging request + response."""

    def _proxy(self):
        # Read request body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b""

        # Build target URL
        target = f"{TARGET_URL}{self.path}"

        # Log request
        ts = datetime.now(timezone.utc).isoformat()
        req_data = body.decode(errors="replace")
        entry = (
            f"\n{'='*80}\n"
            f"[{ts}] {self.command} {self.path}\n"
            f"{'─'*80}\n"
            f"REQUEST BODY ({len(body)} bytes):\n"
        )

        # Pretty-print JSON if possible
        try:
            parsed = json.loads(req_data)
            # Truncate large message content for readability
            entry += json.dumps(parsed, indent=2, ensure_ascii=False)[:20000]
        except (json.JSONDecodeError, ValueError):
            entry += req_data[:5000]

        entry += f"\n{'─'*80}\n"

        # Forward to target
        headers = {
            k: v for k, v in self.headers.items()
            if k.lower() not in ("host", "transfer-encoding")
        }
        headers["Host"] = TARGET_URL.split("//", 1)[-1]

        req = Request(
            target,
            data=body if body else None,
            headers=headers,
            method=self.command,
        )

        try:
            with urlopen(req, timeout=600) as resp:
                resp_body = resp.read()
                status = resp.status

                entry += f"RESPONSE {status} ({len(resp_body)} bytes):\n"
                resp_text = resp_body.decode(errors="replace")
                try:
                    parsed_resp = json.loads(resp_text)
                    entry += json.dumps(parsed_resp, indent=2, ensure_ascii=False)[:20000]
                except (json.JSONDecodeError, ValueError):
                    entry += resp_text[:5000]

                # Send response back to client
                self.send_response(status)
                for header, value in resp.getheaders():
                    if header.lower() not in ("transfer-encoding",):
                        self.send_header(header, value)
                self.end_headers()
                self.wfile.write(resp_body)

        except HTTPError as e:
            resp_body = e.read()
            entry += f"RESPONSE ERROR {e.code} ({len(resp_body)} bytes):\n"
            entry += resp_body.decode(errors="replace")[:5000]

            self.send_response(e.code)
            self.end_headers()
            self.wfile.write(resp_body)

        except URLError as e:
            entry += f"CONNECTION ERROR: {e}\n"
            self.send_response(502)
            self.end_headers()
            self.wfile.write(str(e).encode())

        entry += f"\n{'='*80}\n"

        # Write to log file
        with open(LOG_FILE, "a") as f:
            f.write(entry)

        log.info(f"{self.command} {self.path} → logged")

    def do_GET(self):
        self._proxy()

    def do_POST(self):
        self._proxy()

    def do_PUT(self):
        self._proxy()

    def do_DELETE(self):
        self._proxy()

    def log_message(self, format, *args):
        """Suppress default HTTP log messages."""
        pass


def main():
    parser = argparse.ArgumentParser(description="Debug proxy for Ollama/LM Studio")
    parser.add_argument("--target", default="http://localhost:11434",
                        help="Target URL to proxy to")
    parser.add_argument("--port", type=int, default=18434,
                        help="Port to listen on")
    parser.add_argument("--log-file", default="proxy_debug.log",
                        help="Log file path")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    global TARGET_URL, LOG_FILE
    TARGET_URL = args.target.rstrip("/")
    LOG_FILE = Path(args.log_file)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    server = HTTPServer(("127.0.0.1", args.port), ProxyHandler)
    log.info(f"Debug proxy listening on http://127.0.0.1:{args.port}")
    log.info(f"Forwarding to {TARGET_URL}")
    log.info(f"Logging to {LOG_FILE}")
    log.info("Use ANTHROPIC_BASE_URL=http://localhost:%d in eval1.py", args.port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down.")


if __name__ == "__main__":
    main()
