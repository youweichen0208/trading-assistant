"""Bounded personal notes, kept outside formal research inputs.

Flat IDs and descriptor-relative, no-follow access prevent directory escape.
A process lock serializes edits and backups; revisions use optimistic hashes.
"""
import fcntl
import hashlib
import json
import os
import re
import stat
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

MAX_BYTES = 256_000
MAX_NOTES = 2000


class KnowledgeStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.root.is_symlink():
            raise ValueError('knowledge root cannot be a symlink')

    @contextmanager
    def locked(self):
        directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            lock = os.open('.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600, dir_fd=directory)
            try:
                if os.fstat(lock).st_nlink != 1:
                    raise ValueError('invalid lock')
                fcntl.flock(lock, fcntl.LOCK_EX)
                yield directory
            finally:
                os.close(lock)
        finally:
            os.close(directory)

    @staticmethod
    def _name(note_id):
        if not isinstance(note_id, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}', note_id):
            raise ValueError('note ID must be 1–80 letters, digits, underscores or hyphens')
        return note_id + '.json'

    def _read(self, directory, note_id):
        fd = os.open(self._name(note_id), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(fd, 'rb') as file:
            info = os.fstat(file.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_BYTES:
                raise ValueError('not a bounded regular note')
            return json.loads(file.read(MAX_BYTES + 1))

    def read(self, note_id):
        with self.locked() as directory:
            return self._read(directory, note_id)

    def search(self, query='', limit=20):
        if not isinstance(query, str) or len(query) > 200 or not 1 <= limit <= 100:
            raise ValueError('invalid search query or limit')
        with self.locked() as directory:
            results = []
            for filename in sorted(os.listdir(directory)):
                if not filename.endswith('.json'):
                    continue
                note = self._read(directory, filename[:-5])
                if query.casefold() in (note['title'] + '\n' + note['content']).casefold():
                    results.append({key: note[key] for key in ('id', 'title', 'sha256', 'revision', 'updated_at', 'sources')})
                    if len(results) == limit:
                        break
            return results

    def _write(self, directory, note):
        if not isinstance(note['title'], str) or not 1 <= len(note['title']) <= 200:
            raise ValueError('title must be 1–200 characters')
        if not isinstance(note['content'], str) or not note['content']:
            raise ValueError('content is required')
        if not isinstance(note['sources'], list) or len(note['sources']) > 50:
            raise ValueError('at most 50 sources')
        for source in note['sources']:
            if (not isinstance(source, dict) or not isinstance(source.get('url'), str)
                    or not source['url'].startswith(('https://', 'http://'))
                    or not isinstance(source.get('accessed_at'), str) or not source['accessed_at']):
                raise ValueError('sources need an HTTP URL and accessed_at; use published_at when known')
        note['updated_at'] = datetime.now(timezone.utc).isoformat()
        note.pop('sha256', None)
        encoded = json.dumps(note, ensure_ascii=False, sort_keys=True).encode()
        note['sha256'] = hashlib.sha256(encoded).hexdigest()
        encoded = json.dumps(note, ensure_ascii=False, sort_keys=True).encode()
        if len(encoded) > MAX_BYTES:
            raise ValueError('note exceeds 256 KB')
        temp = '.write-' + uuid.uuid4().hex
        try:
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
            with os.fdopen(fd, 'wb') as file:
                file.write(encoded); file.flush(); os.fsync(file.fileno())
            os.replace(temp, self._name(note['id']), src_dir_fd=directory, dst_dir_fd=directory)
            os.fsync(directory)
        finally:
            try:
                os.unlink(temp, dir_fd=directory)
            except FileNotFoundError:
                pass
        return note

    def save(self, note_id, title, content, sources):
        name = self._name(note_id)
        with self.locked() as directory:
            if name in os.listdir(directory):
                raise ValueError('note exists; read and revise with its hash')
            if len([p for p in os.listdir(directory) if p.endswith('.json')]) >= MAX_NOTES:
                raise ValueError('note capacity reached')
            return self._write(directory, dict(id=note_id, title=title, content=content,
                                               sources=sources, revision=1))

    def revise(self, note_id, content, expected_sha256, sources=None):
        with self.locked() as directory:
            note = self._read(directory, note_id)
            if note['sha256'] != expected_sha256:
                raise ValueError('note changed; read current version first')
            note.update(content=content, revision=note['revision'] + 1)
            if sources is not None:
                note['sources'] = sources
            return self._write(directory, note)

    def delete(self, note_id, expected_sha256):
        with self.locked() as directory:
            if self._read(directory, note_id)['sha256'] != expected_sha256:
                raise ValueError('note changed; read current version first')
            os.unlink(self._name(note_id), dir_fd=directory)
            os.fsync(directory)
        return {'deleted': note_id}
