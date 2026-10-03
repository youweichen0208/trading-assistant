import sqlite3
from integrations.hermes.backup import create_backup, verify_restore
from integrations.hermes.knowledge import KnowledgeStore


def test_backup_restores_databases_memory_and_knowledge_without_secrets(tmp_path):
    home = tmp_path / 'profile'; home.mkdir()
    with sqlite3.connect(home / 'state.db') as db:
        db.execute('CREATE TABLE sessions (id TEXT)')
        db.execute("INSERT INTO sessions VALUES ('conversation-marker')")
    (home / 'memories').mkdir()
    (home / 'memories' / 'USER.md').write_text('Prefers Chinese')
    (home / '.env').write_text('SECRET=never-back-up-here')
    notes = KnowledgeStore(tmp_path / 'knowledge')
    saved = notes.save('apple', 'Apple', 'Source material', [])
    archive = tmp_path / 'backup.tar.gz'
    create_backup(home, notes.root, archive)
    restored = tmp_path / 'restored'
    assert verify_restore(archive, restored)['databases']['state.db'] == 1
    assert KnowledgeStore(restored / 'knowledge').read('apple') == saved
    assert (restored / 'profile/memories/USER.md').read_text() == 'Prefers Chinese'
    assert not (restored / 'profile/.env').exists()
    with sqlite3.connect(restored / 'profile/state.db') as db:
        assert db.execute('SELECT id FROM sessions').fetchone()[0] == 'conversation-marker'
