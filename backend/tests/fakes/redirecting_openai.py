"""A fake OpenAI-compatible server that answers, and a redirector that points at it. Both count their hits.

Used to prove that a redirect from a configured endpoint is never followed: the target's hit count stays at zero.
"""

import json
import ssl
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class Servers:
	"""A target that answers like an OpenAI server and a redirector that points at it, counting hits on each."""

	def __init__(self, tls_context: ssl.SSLContext | None = None):
		self.hits = {"target": 0, "redirector": 0}
		outer = self

		class Target(BaseHTTPRequestHandler):
			def do_POST(self):
				outer.hits["target"] += 1
				length = int(self.headers.get("Content-Length") or 0)
				self.rfile.read(length)
				body = json.dumps({
					"id": "x", "object": "chat.completion", "created": 0, "model": "gpt-4o-mini",
					"choices": [{"index": 0, "message": {"role": "assistant", "content": "answer"}, "finish_reason": "stop"}],
					"usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
				}).encode()
				self.send_response(200)
				self.send_header("Content-Type", "application/json")
				self.send_header("Content-Length", str(len(body)))
				self.end_headers()
				self.wfile.write(body)

			def log_message(self, *args):
				pass

		self.target = HTTPServer(("127.0.0.1", 0), Target)
		if tls_context is not None:
			self.target.socket = tls_context.wrap_socket(self.target.socket, server_side=True)

		class Redirector(BaseHTTPRequestHandler):
			def do_POST(self):
				outer.hits["redirector"] += 1
				length = int(self.headers.get("Content-Length") or 0)
				self.rfile.read(length)
				self.send_response(307)
				self.send_header("Location", f"http://127.0.0.1:{outer.target.server_port}/v1/chat/completions")
				self.send_header("Content-Length", "0")
				self.end_headers()

			def log_message(self, *args):
				pass

		self.redirector = HTTPServer(("127.0.0.1", 0), Redirector)
		for server in (self.target, self.redirector):
			threading.Thread(target=server.serve_forever, daemon=True).start()

	def close(self):
		for server in (self.target, self.redirector):
			server.shutdown()
			server.server_close()

	@property
	def target_base(self):
		return f"http://127.0.0.1:{self.target.server_port}/v1"

	@property
	def redirector_base(self):
		return f"http://127.0.0.1:{self.redirector.server_port}/v1"
