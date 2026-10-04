"""Offline integration against the pinned, separately installed Hermes checkout.

Run with that checkout's Python 3.13. Starts a real native gateway and a mock
OpenAI endpoint; never loads production keys or calls a paid model.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from integrations.hermes.backup import create_backup, verify_restore


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


from assistant_mock_model import MockModel


def verify(checkout):
    from ruamel.yaml import YAML
    assert subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip() == json.loads((ROOT/'upstreams.lock.json').read_text())['hermes']['revision']
    model = ThreadingHTTPServer(('127.0.0.1', 0), MockModel)
    threading.Thread(target=model.serve_forever, daemon=True).start()
    with tempfile.TemporaryDirectory(prefix='youwei-native-') as tmp:
        root = Path(tmp); home = root/'profile'; home.mkdir()
        shutil.copytree(ROOT/'integrations/hermes', home/'plugins/youwei-assistant')
        config = YAML(typ='safe').load((ROOT/'integrations/hermes/config.yaml').read_text())
        port = free_port()
        config['model']['base_url'] = f'http://127.0.0.1:{model.server_port}/v1'
        config['platforms']['api_server'].update(host='127.0.0.1', port=port)
        (home/'config.yaml').write_text(json.dumps(config))
        env = {k: v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL','TMPDIR','SYSTEMROOT')}
        env.update(HOME=str(root), HERMES_HOME=str(home), PYTHONPATH=str(checkout),
                   HERMES_DISABLE_LAZY_INSTALLS='1', API_SERVER_ENABLED='true', API_SERVER_KEY='native-smoke-test-key-123456',
                   YOUWEI_ASSISTANT_LLM_KEY='mock-model-key-123456789',
                   YOUWEI_KNOWLEDGE_DIR=str(root/'knowledge'),
                   YOUWEI_ASSISTANT_CORE_URL='http://127.0.0.1:1', YOUWEI_ASSISTANT_CORE_KEY='mock-core-key-123456789')
        log = open(root/'gateway.log', 'w+')
        def start():
            process = subprocess.Popen([str(checkout/'.venv/bin/hermes'), 'gateway', 'run'], cwd=root, env=env, stdout=log, stderr=log)
            for _ in range(120):
                try:
                    if httpx.get(f'http://127.0.0.1:{port}/health').status_code == 200:
                        return process
                except httpx.TransportError:
                    pass
                if process.poll() is not None:
                    break
                time.sleep(.25)
            process.terminate(); process.wait(timeout=20)
            log.seek(0); raise RuntimeError(log.read()[-10000:])
        process = start()
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', headers={'Authorization':'Bearer '+env['API_SERVER_KEY']}, timeout=60) as client:
                assert client.get('/v1/models').json()['data'][0]['id'] == 'Hermes 美股助手'
                assert httpx.get(f'http://127.0.0.1:{port}/v1/models').status_code == 401
                def call(tool, args):
                    response = client.post('/v1/chat/completions', json={'model':'Hermes 美股助手', 'messages':[
                        {'role':'user','content':'VERIFY:'+json.dumps({'tool':tool,'args':args})}]})
                    assert response.status_code == 200, response.text
                    return json.loads(response.json()['choices'][0]['message']['content'])
                failed_submit = call('youwei_platform', {'action':'submit','arguments':{'ticker':'AAPL','horizon_td':20}})
                assert 'transport failure' in failed_submit['error'], failed_submit
                malformed = client.post('/v1/chat/completions', json={'messages':[]})
                assert malformed.status_code == 400, malformed.text
                with client.stream('POST', '/v1/chat/completions', json={'stream':True,'messages':[{'role':'user','content':'SLOW'}]}) as stopped:
                    assert stopped.status_code == 200
                    assert MockModel.slow_started.wait(10)
                    overflow=client.post('/v1/chat/completions',json={'messages':[{'role':'user','content':'busy probe'}]})
                    assert overflow.status_code == 429, overflow.text
                    # Closing the stream models the frontend Stop/disconnect operation.
                time.sleep(4)
                recovered=client.post('/v1/chat/completions',json={'messages':[{'role':'user','content':'after stop'}]})
                assert recovered.status_code == 200, recovered.text
                saved = call('youwei_knowledge', {'action':'save','arguments':{'note_id':'aapl','title':'Apple source', 'content':'Annual report marker', 'sources':[{'url':'https://www.apple.com/','accessed_at':'2026-10-04'}]}})
                assert saved['revision'] == 1, saved
                recalled = call('youwei_knowledge', {'action':'read','arguments':{'note_id':'aapl'}})
                assert recalled == saved
                revised = call('youwei_knowledge', {'action':'revise','arguments':{'note_id':'aapl','content':'Revised marker','expected_sha256':saved['sha256']}})
                assert revised['revision'] == 2
                call('memory', {'action':'add','target':'user','content':'Native smoke preference marker'})
                assert 'Native smoke preference marker' in (home/'memories/USER.md').read_text()
                create_backup(home, root/'knowledge', root/'backup.tar.gz')
                restored = root/'restored'
                assert verify_restore(root/'backup.tar.gz', restored)['databases']['state.db'] > 0
                assert 'Native smoke preference marker' in (restored/'profile/memories/USER.md').read_text()
                stream = client.post('/v1/chat/completions', json={'model':'Hermes 美股助手','stream':True,'messages':[
                    {'role':'user','content':'first question marker'}, {'role':'assistant','content':'prior reply'},
                    {'role':'user','content':'follow-up marker'}]})
                assert stream.status_code == 200 and 'data: [DONE]' in stream.text, stream.text
                assert any(any(m.get('content') == 'prior reply' for m in h) for h in MockModel.histories)
                process.terminate(); process.wait(timeout=30)
                for database in home.glob('*.db*'):
                    database.unlink()
                for database in (restored/'profile').glob('*.db'):
                    shutil.copy(database, home/database.name)
                shutil.rmtree(root/'knowledge')
                shutil.copytree(restored/'knowledge', root/'knowledge')
                process = start()
                assert call('youwei_knowledge', {'action':'read','arguments':{'note_id':'aapl'}}) == revised
                assert call('youwei_knowledge', {'action':'delete','arguments':{'note_id':'aapl','expected_sha256':revised['sha256']}})['deleted'] == 'aapl'
                assert call('youwei_knowledge', {'action':'search','arguments':{'query':'marker'}}) == []
                print('PASS native discovery/auth/concurrency/stream disconnect/error/tool loop/new-chat recall/revision/stream/full history/memory/backup/restore/restart/delete')
        except Exception:
            log.flush(); log.seek(0); print(log.read()[-10000:]); raise
        finally:
            process.terminate(); process.wait(timeout=30); log.close(); model.shutdown()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('checkout', type=Path)
    verify(parser.parse_args().checkout.resolve())
