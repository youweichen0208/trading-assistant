import threading
from http.server import ThreadingHTTPServer

import httpx

from integrations.hermes.workbench import make_handler


def test_readonly_authenticated_skill_interface():
    seen = []
    def read(name):
        seen.append(name)
        return {'name': name, 'content': 'hello'}
    server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler('offline-test-key', lambda: [{'name': 'test'}], read))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{server.server_port}') as client:
            assert client.get('/skills').status_code == 401
            client.headers['Authorization'] = 'Bearer offline-test-key'
            assert client.get('/skills').json() == {'data': [{'name': 'test'}]}
            assert client.get('/skills/test').json()['content'] == 'hello'
            assert client.get('/skills/%2e%2e%2fconfig.yaml').status_code == 404
            assert client.get('/config').status_code == 404
            assert client.post('/skills', json={}).status_code == 501
            assert seen == ['test']
    finally:
        server.shutdown(); server.server_close(); thread.join()
