"""Protocol smoke against an already running real native OS backend, never a mock."""
import hashlib
import http.client
import json
import socket
import time
from pathlib import Path


class LiveHTTP:
    def __init__(self, recorder, port, capability):
        self.recorder, self.port, self.capability = recorder, int(port), capability
        recorder.secrets.append(capability)
        self.received = {}

    def request(self, method, route, value=None, raw=None, headers=None, expected=200):
        body = raw if raw is not None else (json.dumps(value, ensure_ascii=False).encode('utf-8') if value is not None else b'')
        h = {'Content-Type': 'application/json'} if raw is None else {'Content-Type': 'application/octet-stream'}
        h.update(headers or {})
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=30)
        try:
            connection.request(method, route, body=body if method not in ['GET', 'HEAD'] else None, headers=h)
            response = connection.getresponse()
            data = response.read(8 * 2**20 + 1)
            if len(data) > 8 * 2**20:
                raise AssertionError('Smoke response exceeded 8 MiB bound')
            if response.status != expected:
                raise AssertionError(method + ' response ' + str(response.status) + ', expected ' + str(expected))
            return data
        finally:
            connection.close()

    def json(self, method, route, value=None, headers=None, expected=200):
        result = json.loads(self.request(method, route, value=value, headers=headers, expected=expected))
        if isinstance(result, dict):
            for name in ['token', 'code', 'statusToken', 'offerKey']:
                if isinstance(result.get(name), str):
                    self.recorder.secrets.append(result[name])
        return result

    def desktop(self, route, value=None):
        return self.json('POST', route, value, {'X-Desktop-Token': self.capability})

    def create(self, files):
        return self.json('POST', '/api/transfers', {'files': [{'name': n, 'size': len(b), 'type': 'application/octet-stream'} for n, b in files]},
                         {'X-Desktop-Token': self.capability}, expected=201)

    def transfer(self, directory, round):
        files = [('Rỗng.bin', b''), ('Tài liệu có khoảng trắng.txt', 'FlowDrop — native Windows SHA-256'.encode()),
                 ('pattern.bin', bytes(i % 251 for i in range(1024 * 1024 + 17)))]
        created = self.create(files)
        code, token = created['code'], created['token']
        for remote, (name, data) in zip(created['files'], files):
            self.request('PUT', '/api/transfers/' + code + '/files/' + remote['id'], raw=data, headers={'X-Upload-Token': token}, expected=200)
        self.json('POST', '/api/transfers/' + code + '/complete', headers={'X-Upload-Token': token})
        metadata = self.json('GET', '/api/transfers/' + code)
        evidence = []
        for remote, (name, data) in zip(metadata['files'], files):
            actual = self.request('GET', '/api/transfers/' + code + '/files/' + remote['id'])
            assert hashlib.sha256(actual).digest() == hashlib.sha256(data).digest(), 'Live Windows HTTP bytes changed'
        before = {p for p in Path(directory).iterdir() if p.is_file()}
        self.desktop('/api/desktop/receive', {'code': code})
        after = {p for p in Path(directory).iterdir() if p.is_file()}
        added = after - before
        assert len(added) == len(files), 'Actual permanent receive missing files or overwrote existing files'
        expected_hashes = sorted(hashlib.sha256(data).hexdigest() for _, data in files)
        actual_hashes = sorted(hashlib.sha256(path.read_bytes()).hexdigest() for path in added)
        assert expected_hashes == actual_hashes, 'Actual saved Windows files have different SHA-256'
        for path in after:
            value = hashlib.sha256(path.read_bytes()).hexdigest()
            if path in self.received:
                assert value == self.received[path], 'Duplicate transfer overwrote previous data'
            self.received[path] = value
        for path in added:
            evidence.append({'round': round, 'name': path.name, 'size': path.stat().st_size, 'sha256': self.received[path]})
        return evidence

    def cancel(self):
        created = self.create([('cancel.bin', b'pending')])
        self.json('DELETE', '/api/transfers/' + created['code'], headers={'X-Upload-Token': created['token']})
        self.request('GET', '/api/transfers/' + created['code'], expected=404)
        return {'revoked': True, 'metadata_after_cancel': 404}

    def disconnect(self):
        created = self.create([('disconnected.bin', b'x' * 65536)])
        code, token, file = created['code'], created['token'], created['files'][0]['id']
        with socket.create_connection(('127.0.0.1', self.port), timeout=10) as connection:
            request = ('PUT /api/transfers/' + code + '/files/' + file + ' HTTP/1.1\r\nHost: 127.0.0.1:' + str(self.port)
                + '\r\nX-Upload-Token: ' + token + '\r\nContent-Length: 65536\r\nContent-Type: application/octet-stream\r\nConnection: close\r\n\r\n').encode()
            connection.sendall(request + b'abc')
        time.sleep(.5)
        self.request('POST', '/api/transfers/' + code + '/complete', headers={'X-Upload-Token': token}, expected=409)
        self.request('GET', '/api/transfers/' + code + '/files/' + file, expected=409)
        self.json('DELETE', '/api/transfers/' + code, headers={'X-Upload-Token': token})
        return {'declared_bytes': 65536, 'sent_bytes': 3, 'complete_status': 409, 'partial_file_status': 409}

    def invalid(self):
        bad = {'files': [{'name': 'invalid.bin', 'size': -1}]}
        self.json('POST', '/api/transfers', bad, expected=403)
        self.json('POST', '/api/transfers', bad, {'X-Desktop-Token': 'synthetic-incorrect-capability'}, expected=403)
        self.json('POST', '/api/transfers', bad, {'X-Desktop-Token': self.capability}, expected=400)
        self.json('GET', '/api/desktop/settings', expected=403)
        return {'missing_capability': 403, 'incorrect_capability': 403, 'invalid_metadata': 400, 'protected_settings': 403}
