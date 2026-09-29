# Author: Ziyi Liu (zl6722)
"""Persistent authoritative server for the lab's text-based UDP protocol."""
import os
import socket
import sqlite3
from pathlib import Path
from common import fields, hostname, ipv4, port, record


def main():
    db_path = Path(os.getenv('DB_PATH', 'records.sqlite3'))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        db.execute('CREATE TABLE IF NOT EXISTS records (name TEXT PRIMARY KEY, address TEXT NOT NULL, ttl INTEGER NOT NULL)')
        db.commit()
        sock.bind((os.getenv('HOST', '0.0.0.0'), port(os.getenv('PORT', '53533'))))
        print(f'AS listening on UDP {sock.getsockname()[1]}', flush=True)
        while True:
            message, peer = sock.recvfrom(4096)
            try:
                request = fields(message)
                if request.get('TYPE') != 'A':
                    raise ValueError('Only type A is supported')
                name = hostname(request.get('NAME'))
                if set(request) == {'TYPE', 'NAME', 'VALUE', 'TTL'}:
                    address = ipv4(request['VALUE'])
                    ttl = int(request['TTL'])
                    if not 0 <= ttl <= 2147483647:
                        raise ValueError('Invalid TTL')
                    db.execute('INSERT INTO records VALUES (?, ?, ?) ON CONFLICT(name) DO UPDATE SET address=excluded.address, ttl=excluded.ttl', (name, address, ttl))
                    db.commit()
                    response = b'STATUS=OK\n'
                elif set(request) == {'TYPE', 'NAME'}:
                    row = db.execute('SELECT address, ttl FROM records WHERE name=?', (name,)).fetchone()
                    response = record(name, row[0], row[1]) if row else b'ERROR=NOT_FOUND\n'
                else:
                    raise ValueError('Invalid field set')
            except (ValueError, UnicodeError, TypeError):
                response = b'ERROR=BAD_REQUEST\n'
            except sqlite3.Error:
                response = b'ERROR=STORAGE_FAILURE\n'
            sock.sendto(response, peer)


if __name__ == '__main__':
    main()
