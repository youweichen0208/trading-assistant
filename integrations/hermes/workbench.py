"""Read-only skill catalogue for the WebUI workbench, using pinned Hermes readers.

Runs as a separate container with a read-only profile mount. No model, tool dispatch,
inline shell preprocessing, skill writes, gateway controls or credential read APIs.
"""
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, unquote


def catalogue():
    from tools.skills_tool import _find_all_skills, _sort_skills
    return _sort_skills(_find_all_skills(skip_disabled=False))


def content(name):
    from tools.skills_tool import skill_view
    if name not in {skill['name'] for skill in catalogue()}:
        raise KeyError(name)
    # Critical: SKILL.md can contain inline shell templates. Display never evaluates them.
    result = json.loads(skill_view(name, preprocess=False))
    if not result.get('success'):
        raise KeyError(name)
    return {key: result.get(key) for key in ('name', 'description', 'content', 'tags')}


def make_handler(key, list_skills=catalogue, read_skill=content):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def respond(self, code, value):
            data = json.dumps(value, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + key):
                return self.respond(401, {'error': 'Unauthorized'})
            path = urlsplit(self.path).path
            try:
                if path == '/skills':
                    return self.respond(200, {'data': list_skills()})
                if path.startswith('/skills/'):
                    name = unquote(path[len('/skills/'):])
                    if not name or len(name) > 200 or '/' in name or '\\' in name or name in {'.', '..'}:
                        return self.respond(404, {'error': 'Unknown skill'})
                    return self.respond(200, read_skill(name))
                return self.respond(404, {'error': 'Not found'})
            except KeyError:
                return self.respond(404, {'error': 'Unknown or unavailable skill'})
            except Exception:
                return self.respond(500, {'error': 'Skill reader unavailable'})

    return Handler


def main():
    key = os.environ.get('API_SERVER_KEY', '')
    if len(key) < 16:
        raise SystemExit('API_SERVER_KEY must be configured (at least 16 characters)')
    server = ThreadingHTTPServer(('0.0.0.0', int(os.environ.get('WORKBENCH_PORT', '8643'))), make_handler(key))
    server.serve_forever()


if __name__ == '__main__':
    main()
