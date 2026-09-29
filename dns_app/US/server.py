# Author: Ziyi Liu (zl6722)
"""Resolve FS through AS over UDP, then forward an HTTP Fibonacci request."""
import http.client
import os
import socket
from http.server import ThreadingHTTPServer
from urllib.parse import urlencode, urlsplit
from common import HandlerBase, exchange, fields, hostname, ipv4, number, port


class Handler(HandlerBase):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/health':
            return self.reply(200, 'OK')
        if path != '/fibonacci':
            return self.reply(404, 'Not found')
        try:
            data = self.parameters(('hostname', 'fs_port', 'number', 'as_ip', 'as_port'))
            name = hostname(data['hostname'])
            fs_port = port(data['fs_port'])
            as_port = port(data['as_port'])
            n = number(data['number'])
        except ValueError as exc:
            return self.reply(400, exc)
        try:
            answer = fields(exchange(data['as_ip'], as_port, f'TYPE=A\nNAME={name}\n'.encode('ascii')))
            if answer.get('ERROR') == 'NOT_FOUND':
                return self.reply(404, 'Hostname is not registered')
            if set(answer) != {'TYPE', 'NAME', 'VALUE', 'TTL'} or answer['TYPE'] != 'A' or answer['NAME'] != name:
                return self.reply(502, 'Invalid AS response')
            address = ipv4(answer['VALUE'])
            if int(answer['TTL']) < 0:
                raise ValueError('Invalid TTL')
            connection = http.client.HTTPConnection(address, fs_port, timeout=3)
            try:
                connection.request('GET', '/fibonacci?' + urlencode({'number': n}))
                response = connection.getresponse()
                body = response.read().decode('utf-8')
                self.reply(response.status if response.status in (200, 400) else 502, body)
            finally:
                connection.close()
        except socket.timeout:
            self.reply(504, 'Upstream server timed out')
        except (OSError, ValueError, UnicodeError, http.client.HTTPException):
            self.reply(502, 'Upstream server is unavailable or returned invalid data')


if __name__ == '__main__':
    server = ThreadingHTTPServer((os.getenv('HOST', '0.0.0.0'), port(os.getenv('PORT', '8080'))), Handler)
    print(f'US listening on HTTP {server.server_port}', flush=True)
    server.serve_forever()
