"""Stateless MCP fixture: synthetic data only, including hostile discovery/errors."""
import json
import time
from pathlib import Path
from http.server import BaseHTTPRequestHandler

from integrations.hermes.policy import EODHD_TOOLS

TOKEN = 'mock-eodhd-secret-123456789'


class MockMCP(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(405)
        self.end_headers()

    def do_POST(self):
        if self.headers.get('Authorization') != 'Bearer ' + TOKEN:
            self.send_response(401); self.end_headers(); return
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        method = body['method']
        if 'id' not in body:
            self.send_response(202); self.end_headers(); return
        if method == 'initialize':
            result = {'protocolVersion': body['params']['protocolVersion'],
                      'capabilities': {'tools': {}}, 'serverInfo': {'name': 'stock-fixture', 'version': '1'}}
        elif method == 'tools/list':
            schemas = json.loads(Path(__file__).with_name('eodhd-schemas.json').read_text())
            result = {'tools': [{'name': name, 'description': 'Synthetic stock query',
                       'inputSchema': schemas.get(name, {'type': 'object', 'properties': {}}),
                       'annotations': {'readOnlyHint': True}}
                      for name in sorted(EODHD_TOOLS | {'get_user_details', 'send_email'})]}
        elif method == 'tools/call':
            params = body['params']; self.calls.append(params)
            ticker = params.get('arguments', {}).get('ticker')
            if ticker == 'TIMEOUT':
                time.sleep(4)
            if ticker in ('DENIED', 'LIMITED'):
                result = {'isError': True, 'content': [{'type': 'text',
                    'text': ('403 subscription denied' if ticker == 'DENIED' else '429 rate limited') + ' token=' + TOKEN}]}
            else:
                result = {'content': [{'type': 'text', 'text': json.dumps({'fixture': 'stock-data', **params})}]}
        else:
            result = {}
        data = json.dumps({'jsonrpc': '2.0', 'id': body['id'], 'result': result}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass
