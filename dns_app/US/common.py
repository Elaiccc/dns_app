# Author: Ziyi Liu (zl6722)
"""Shared helpers, copied into each independent Docker build context."""
import ipaddress
import re
import socket
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlsplit


def hostname(value):
    if not isinstance(value, str):
        raise ValueError('Invalid hostname')
    value = value.rstrip('.').lower()
    labels = value.split('.')
    if len(value) > 253 or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', x) for x in labels):
        raise ValueError('Invalid hostname')
    return value


def port(value):
    if isinstance(value, bool) or not re.fullmatch(r'[0-9]+', str(value)):
        raise ValueError('Invalid port')
    value = int(value)
    if not 1 <= value <= 65535:
        raise ValueError('Port must be between 1 and 65535')
    return value


def ipv4(value):
    if not isinstance(value, str):
        raise ValueError('Invalid IPv4 address')
    return str(ipaddress.IPv4Address(value))


def number(value):
    if not isinstance(value, str) or not re.fullmatch(r'[+]?[0-9]+', value):
        raise ValueError('number must be a nonnegative integer')
    return int(value)


def fields(data):
    result = {}
    for token in data.decode('ascii').split():
        key, value = token.split('=', 1)
        if key in result or not value:
            raise ValueError('Invalid DNS fields')
        result[key] = value
    return result


def record(name, address, ttl):
    return f'TYPE=A\nNAME={name} VALUE={address} TTL={ttl}\n'.encode('ascii')


def exchange(host, udp_port, message, timeout=2.0):
    # Connected UDP restricts received datagrams to the requested server.
    if not isinstance(host, str) or not host.strip():
        raise ValueError('Invalid AS address')
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        sock.connect((host, port(udp_port)))
        sock.send(message)
        return sock.recv(4096)


class HandlerBase(BaseHTTPRequestHandler):
    def reply(self, status, message):
        body = (str(message).rstrip('\n') + '\n').encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def parameters(self, names):
        parsed = urlsplit(self.path)
        values = parse_qs(parsed.query, keep_blank_values=True)
        if any(len(values.get(k, [])) != 1 or not values[k][0] for k in names):
            raise ValueError('Missing, empty, or repeated required parameter')
        return {k: values[k][0] for k in names}
