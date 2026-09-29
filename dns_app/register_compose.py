# Author: Ziyi Liu (zl6722)
"""Run through docker compose exec -T fs python - < register_compose.py."""
import http.client
import json
import socket
import time

payload = json.dumps({'hostname': 'fibonacci.com', 'ip': socket.gethostbyname('fs'), 'as_ip': 'as', 'as_port': 53533})
for attempt in range(10):
    connection = http.client.HTTPConnection('localhost', 9090, timeout=5)
    try:
        connection.request('PUT', '/register', body=payload, headers={'Content-Type': 'application/json'})
        response = connection.getresponse()
        body = response.read().decode().strip()
        if response.status == 201:
            print('201 ' + body)
            break
    except OSError:
        pass
    finally:
        connection.close()
    time.sleep(0.5)
else:
    raise SystemExit('Registration failed; check docker compose logs.')
