"""Shared fixtures. The stub Messages API lets tests drive the real anthropic SDK without network access."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest


class _StubMessagesHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers["Content-Length"])
        self.server.requests.append(json.loads(self.rfile.read(length)))
        payload = json.dumps(self.server.replies.pop(0)).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):  # keep test output quiet
        pass


def stub_message(content, stop_reason="tool_use"):
    """A Messages API response body with the given content blocks."""
    return {
        "id": "msg_stub",
        "type": "message",
        "role": "assistant",
        "model": "stub-model",
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 100, "output_tokens": 20},
    }


@pytest.fixture
def stub_api(monkeypatch):
    """A local HTTP server standing in for the Messages API.

    Set ``server.replies`` to the responses to return in order; every request body is recorded in
    ``server.requests``. Localhost bypasses any sandbox proxy.
    """
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    server = HTTPServer(("127.0.0.1", 0), _StubMessagesHandler)
    server.requests = []
    server.replies = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
