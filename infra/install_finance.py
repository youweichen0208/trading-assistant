"""Run with the target Hermes Python; preserve every pre-existing distribution."""
import hashlib
from importlib.metadata import distributions
import json
from pathlib import Path
import re
import subprocess
import sys

root = Path(sys.argv[1]).resolve()
lock = json.loads((root/'upstreams.lock.json').read_text())['trading_core']
wheel = root/lock['wheel']
assert hashlib.sha256(wheel.read_bytes()).hexdigest() == lock['wheel_sha256'], 'wheel hash mismatch'
def versions():
    return {re.sub(r'[-_.]+','-',d.metadata['Name']).lower():d.version for d in distributions()}
before = versions()
requirements = root/lock['requirements']
for name, version in re.findall(r'^([\w-]+)==([^\s]+)',requirements.read_text(),re.M):
    if name in before and before[name] != version:
        raise SystemExit(f'upstream dependency conflict: {name}')
subprocess.run(['uv','--no-config','pip','install','--python',sys.executable,'--require-hashes','--no-deps','-r',str(requirements)],check=True)
subprocess.run(['uv','--no-config','pip','install','--python',sys.executable,'--no-deps',str(wheel)],check=True)
after = versions()
assert all(after.get(name)==version for name,version in before.items()), 'upstream packages changed'
subprocess.run(['uv','--no-config','pip','check','--python',sys.executable],check=True)
print('PASS: wheel hash, dependency compatibility and unchanged upstream versions')
