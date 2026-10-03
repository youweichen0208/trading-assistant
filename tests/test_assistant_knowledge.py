from pathlib import Path

import pytest

from integrations.hermes.knowledge import KnowledgeStore


def test_knowledge_lifecycle_and_restart(tmp_path):
    store = KnowledgeStore(tmp_path)
    created = store.save('apple', 'Apple sources', 'Annual report notes',
                         [{'url': 'https://www.apple.com/', 'accessed_at': '2026-10-04', 'published_at': '2026-09-30'}])
    restarted = KnowledgeStore(tmp_path)
    assert restarted.search('annual')[0]['id'] == 'apple'
    assert restarted.read('apple') == created
    revised = restarted.revise('apple', 'Corrected notes', created['sha256'])
    assert revised['revision'] == 2
    assert revised['sources'] == created['sources']
    with pytest.raises(ValueError):
        restarted.delete('apple', created['sha256'])
    restarted.delete('apple', revised['sha256'])
    assert restarted.search('apple') == []


@pytest.mark.parametrize('name', ['../secret', '/tmp/secret', 'a/b', '.', 'x\\y'])
def test_knowledge_rejects_paths(tmp_path, name):
    with pytest.raises(ValueError):
        KnowledgeStore(tmp_path).read(name)


def test_knowledge_rejects_symlinks(tmp_path):
    root = tmp_path / 'notes'; root.mkdir()
    secret = tmp_path / 'secret'; secret.write_text('private')
    (root / 'evil.json').symlink_to(secret)
    store = KnowledgeStore(root)
    with pytest.raises((ValueError, OSError)):
        store.read('evil')
    with pytest.raises((ValueError, OSError)):
        store.save('evil', 'x', 'x', [])
    assert secret.read_text() == 'private'
