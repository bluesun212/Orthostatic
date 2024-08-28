from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from functools import partial

import threading


class RequestHandler(ThreadingMixIn, SimpleHTTPRequestHandler):
    def log_message(self, _, *args):
        pass  # TODO


class Server:
    def __init__(self, port, dst):
        self.running = True
        self.port = port
        self.dst = dst

        cls = partial(RequestHandler, directory=self.dst)
        self.server = ThreadingHTTPServer(('', self.port), cls)

        t = threading.Thread(target=self._run)
        t.start()

    def stop(self):
        self.server.shutdown()

    def _run(self):
        self.server.serve_forever(0.05)
