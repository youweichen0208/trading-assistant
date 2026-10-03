"""Consistent per-SQLite backup + locked knowledge snapshot, with restore checks.

No credentials/config/plugins/logs in this archive. Databases are individually
consistent; this is not a cross-store transactional snapshot or off-host backup.
"""
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tarfile
import tempfile

if __package__:
    from .knowledge import KnowledgeStore
else:
    from knowledge import KnowledgeStore


def _copy_regular_tree(source, target):
    target.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        return
    if source.is_symlink():
        raise ValueError('symlink in assistant backup')
    for child in source.iterdir():
        if child.is_symlink():
            raise ValueError('symlink in assistant backup')
        if child.is_dir():
            _copy_regular_tree(child, target / child.name)
        elif child.is_file():
            shutil.copyfile(child, target / child.name)
        else:
            raise ValueError('special file in assistant backup')


def create_backup(profile, knowledge, destination):
    profile, knowledge, destination = Path(profile), Path(knowledge), Path(destination)
    if not (profile / 'state.db').is_file() or not knowledge.is_dir():
        raise ValueError('assistant state/knowledge missing')
    with tempfile.TemporaryDirectory() as temporary:
        stage = Path(temporary)
        (stage / 'profile').mkdir()
        for source in profile.glob('*.db'):
            if source.is_symlink():
                raise ValueError('database symlink')
            with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as src:
                with sqlite3.connect(stage / 'profile' / source.name) as dst:
                    src.backup(dst)
                    if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                        raise ValueError('database integrity failure')
        for folder in ('memories', 'sessions'):
            _copy_regular_tree(profile / folder, stage / 'profile' / folder)
        store = KnowledgeStore(knowledge)
        with store.locked():
            _copy_regular_tree(knowledge, stage / 'knowledge')
        (stage / 'knowledge' / '.lock').unlink(missing_ok=True)
        manifest = {str(p.relative_to(stage)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in stage.rglob('*') if p.is_file()}
        (stage / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True))
        with tarfile.open(destination, 'w:gz') as archive:
            for child in stage.iterdir():
                archive.add(child, arcname=child.name)
    destination.chmod(0o600)


def verify_restore(archive_path, destination):
    destination = Path(destination)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('restore destination must be empty')
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path) as archive:
        for member in archive.getmembers():
            if not (member.isfile() or member.isdir()):
                raise ValueError('non-regular backup member')
        archive.extractall(destination, filter='data')
    manifest = json.loads((destination / 'manifest.json').read_text())
    actual = {str(p.relative_to(destination)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in destination.rglob('*') if p.is_file() and p.name != 'manifest.json'}
    if manifest != actual or 'profile/state.db' not in actual:
        raise ValueError('backup manifest mismatch')
    counts = {}
    for database in (destination / 'profile').glob('*.db'):
        with sqlite3.connect(database) as db:
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('restored database is corrupt')
            counts[database.name] = db.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
    notes = KnowledgeStore(destination / 'knowledge').search('', limit=100)
    return {'databases': counts, 'notes_checked_up_to_100': len(notes), 'files': len(actual)}


if __name__ == '__main__':
    import argparse
    import os
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['create', 'verify'])
    parser.add_argument('archive', type=Path)
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args()
    if args.action == 'create':
        create_backup(Path(os.environ['HERMES_HOME']), Path(os.environ['YOUWEI_KNOWLEDGE_DIR']), args.archive)
    else:
        if args.destination is None:
            parser.error('--destination is required for verify')
        print(json.dumps(verify_restore(args.archive, args.destination)))
