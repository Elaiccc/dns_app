# Author: Ziyi Liu (zl6722)
"""Real HTTP/UDP integration tests; no third-party packages required."""
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent


def free_port(kind=socket.SOCK_STREAM):
    with socket.socket(socket.AF_INET, kind) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.log = open(Path(cls.tmp.name) / 'servers.log', 'wb')
        cls.ports = {'AS': free_port(socket.SOCK_DGRAM), 'FS': free_port(), 'US': free_port()}
        cls.processes = {}
        for service in cls.ports:
            cls.start(service)
        cls.register('fibonacci.com')

    @classmethod
    def start(cls, service):
        env = dict(os.environ, HOST='127.0.0.1', PORT=str(cls.ports[service]), DB_PATH=str(Path(cls.tmp.name) / 'records.sqlite3'))
        cls.processes[service] = subprocess.Popen([sys.executable, 'server.py'], cwd=ROOT / service, env=env, stdout=cls.log, stderr=cls.log)
        for _ in range(80):
            try:
                if service == 'AS':
                    cls.udp(b'TYPE=A\nNAME=health.invalid\n', timeout=0.1)
                else:
                    cls.http(service, 'GET', '/health')
                return
            except OSError:
                time.sleep(0.05)
        raise RuntimeError(f'{service} did not start')

    @classmethod
    def tearDownClass(cls):
        for process in cls.processes.values():
            process.terminate()
        for process in cls.processes.values():
            process.wait(timeout=5)
        cls.log.close()
        cls.tmp.cleanup()

    @classmethod
    def http(cls, service, method, path, body=None):
        conn = http.client.HTTPConnection('127.0.0.1', cls.ports[service], timeout=5)
        try:
            conn.request(method, path, body=body, headers={'Content-Type': 'application/json'})
            response = conn.getresponse()
            return response.status, response.read().decode().strip()
        finally:
            conn.close()

    @classmethod
    def udp(cls, message, timeout=2):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            sock.connect(('127.0.0.1', cls.ports['AS']))
            sock.send(message)
            return sock.recv(4096)

    @classmethod
    def register(cls, name):
        return cls.http('FS', 'PUT', '/register', json.dumps({'hostname': name, 'ip': '127.0.0.1', 'as_ip': '127.0.0.1', 'as_port': str(cls.ports['AS'])}))

    def params(self, **changes):
        data = {'hostname': 'fibonacci.com', 'fs_port': self.ports['FS'], 'number': 10, 'as_ip': '127.0.0.1', 'as_port': self.ports['AS']}
        data.update(changes)
        return data

    def test_01_registration_and_exact_dns_response(self):
        self.assertEqual(self.register('fibonacci.com'), (201, 'Registered'))
        self.assertEqual(self.udp(b'TYPE=A\nNAME=fibonacci.com\n'), b'TYPE=A\nNAME=fibonacci.com VALUE=127.0.0.1 TTL=10\n')

    def test_02_direct_and_end_to_end_fibonacci(self):
        for n, expected in [(0, '0'), (1, '1'), (2, '1'), (10, '55'), (100, '354224848179261915075')]:
            with self.subTest(n=n):
                self.assertEqual(self.http('FS', 'GET', f'/fibonacci?number={n}'), (200, expected))
                self.assertEqual(self.http('US', 'GET', '/fibonacci?' + urlencode(self.params(number=n))), (200, expected))

    def test_03_us_all_missing_parameters(self):
        for key in self.params():
            with self.subTest(missing=key):
                data = self.params()
                del data[key]
                self.assertEqual(self.http('US', 'GET', '/fibonacci?' + urlencode(data))[0], 400)

    def test_04_invalid_numbers_and_ports(self):
        for value in ['abc', '1.5', '-1', '', '1e2']:
            with self.subTest(number=value):
                self.assertEqual(self.http('FS', 'GET', '/fibonacci?' + urlencode({'number': value}))[0], 400)
                self.assertEqual(self.http('US', 'GET', '/fibonacci?' + urlencode(self.params(number=value)))[0], 400)
        self.assertEqual(self.http('FS', 'GET', '/fibonacci')[0], 400)
        self.assertEqual(self.http('US', 'GET', '/fibonacci?' + urlencode(self.params(fs_port=70000)))[0], 400)

    def test_05_invalid_registration_and_dns(self):
        for body in ['not json', '[]', '{}', '{"hostname":"fibonacci.com","ip":"not-an-ip","as_ip":"127.0.0.1","as_port":53533}']:
            with self.subTest(body=body):
                self.assertEqual(self.http('FS', 'PUT', '/register', body)[0], 400)
        for message in [b'TYPE=AAAA\nNAME=a.com\n', b'bad', b'TYPE=A\nNAME=a.com VALUE=not-ip TTL=10\n']:
            with self.subTest(message=message):
                self.assertEqual(self.udp(message), b'ERROR=BAD_REQUEST\n')

    def test_06_unknown_hostname(self):
        self.assertEqual(self.udp(b'TYPE=A\nNAME=missing.invalid\n'), b'ERROR=NOT_FOUND\n')
        self.assertEqual(self.http('US', 'GET', '/fibonacci?' + urlencode(self.params(hostname='missing.invalid')))[0], 404)

    def test_07_persistence_after_as_restart(self):
        self.assertEqual(self.udp(b'TYPE=A\nNAME=persist.test VALUE=192.0.2.10 TTL=10\n'), b'STATUS=OK\n')
        self.processes['AS'].terminate()
        self.processes['AS'].wait(timeout=5)
        self.start('AS')
        self.assertEqual(self.udp(b'TYPE=A\nNAME=persist.test\n'), b'TYPE=A\nNAME=persist.test VALUE=192.0.2.10 TTL=10\n')
        self.assertEqual(self.http('US', 'GET', '/fibonacci?' + urlencode(self.params())), (200, '55'))

    def test_08_dns_timeout(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as blackhole:
            blackhole.bind(('127.0.0.1', 0))
            query = urlencode(self.params(as_port=blackhole.getsockname()[1]))
            self.assertEqual(self.http('US', 'GET', '/fibonacci?' + query)[0], 504)


if __name__ == '__main__':
    unittest.main(verbosity=2)
