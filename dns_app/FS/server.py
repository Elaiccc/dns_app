# Author: Ziyi Liu (zl6722)
"""Fibonacci HTTP server and UDP registration client."""
import json
import os
import socket
import sys
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit
from common import HandlerBase, exchange, hostname, ipv4, number, port, record


def fibonacci(n):
    # Fast doubling: F(0)=0 and F(1)=1.
    a, b = 0, 1
    for bit in bin(n)[2:]:
        c = a * (2 * b - a)
        d = a * a + b * b
        a, b = (c, d) if bit == '0' else (d, c + d)
    return a


class Handler(HandlerBase):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/health':
            return self.reply(200, 'OK')
        if path != '/fibonacci':
            return self.reply(404, 'Not found')
        try:
            n = number(self.parameters(('number',))['number'])
            self.reply(200, fibonacci(n))
        except ValueError as exc:
            self.reply(400, exc)

    def do_PUT(self):
        if urlsplit(self.path).path != '/register':
            return self.reply(404, 'Not found')
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 8192:
                raise ValueError('Expected a JSON body of at most 8192 bytes')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict) or not all(k in data for k in ('hostname', 'ip', 'as_ip', 'as_port')):
                raise ValueError('hostname, ip, as_ip, and as_port are required')
            name = hostname(data['hostname'])
            address = ipv4(data['ip'])
            ack = exchange(data['as_ip'], port(data['as_port']), record(name, address, 10))
            if ack != b'STATUS=OK\n':
                return self.reply(502, 'AS rejected the registration')
            self.reply(201, 'Registered')
        except (ValueError, UnicodeError, TypeError) as exc:
            self.reply(400, exc)
        except socket.timeout:
            self.reply(504, 'AS timed out')
        except OSError:
            self.reply(502, 'AS is unavailable')


if __name__ == '__main__':
    if hasattr(sys, 'set_int_max_str_digits'):
        sys.set_int_max_str_digits(0)
    server = ThreadingHTTPServer((os.getenv('HOST', '0.0.0.0'), port(os.getenv('PORT', '9090'))), Handler)
    print(f'FS listening on HTTP {server.server_port}', flush=True)
    server.serve_forever()
