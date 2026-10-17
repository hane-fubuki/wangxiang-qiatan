"""One canonical local origin, with a read-only redirect for old bookmarks."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

APP_PORT = 8765
LEGACY_PORT = 8881


def canonical_port(port):
    return APP_PORT if port == LEGACY_PORT else port


def create_local_redirect(port=LEGACY_PORT, target_port=APP_PORT):
    if type(target_port) is not int or not 1 <= target_port <= 65535:
        raise ValueError("无效的本机服务端口")

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format, *args):
            pass

        def _reply(self, status, location=None):
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            if location:
                self.send_header("Location", location)
            self.end_headers()
            self.close_connection = True

        def do_GET(self):
            hosts = self.headers.get_all("Host", [])
            allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if len(hosts) != 1 or hosts[0] not in allowed:
                return self._reply(403)
            original = self.requestline.split()[1]
            if (original != self.path or not self.path.startswith("/") or self.path.startswith("//")
                    or "\\" in self.path or len(self.path) > 2048
                    or any(ord(c) < 32 or ord(c) == 127 for c in self.path)):
                return self._reply(400)
            self._reply(307, f"http://127.0.0.1:{target_port}{self.path}")

        do_HEAD = do_GET

        def do_POST(self):
            # Do not replay a pending chat action across origins during migration.
            self._reply(409)

        do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_POST

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server
