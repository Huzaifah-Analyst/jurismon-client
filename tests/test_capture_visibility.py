import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from db.repository import Repository
from scripts.audit_capture_quality import audit, change_visibility
from playwright.sync_api import expect
from tests.test_frontend_crawl_polling import local_browser


def test_quarantine_and_restore_preserve_history_and_other_reasons(tmp_path):
    repo = Repository(db_path=str(tmp_path / 'visibility.db'))
    repo.supabase = None
    doc = repo.get_or_create_document('qa', 'Ordinance', 'https://example.invalid/law')
    bad = repo.create_snapshot(doc['id'], 1, 'bad', '', '')
    good = repo.create_snapshot(doc['id'], 2, 'good', 'Section 1: Setbacks', 'Section 1: Setbacks')
    diff = repo.save_diff(doc['id'], bad['id'], good['id'], {'total_added': 1, 'added': [{'text': 'Setbacks'}]})
    unrelated = repo.create_snapshot(doc['id'], 3, 'other', 'Other text', 'Other text')
    repo.set_capture_visibility([unrelated['id']], False, 'other-review')
    applied = change_visibility(repo, audit(repo))
    assert applied['affected'] == {'snapshots': 1, 'diffs': 1}
    result = repo.search_snapshots_and_diffs('')
    assert result['total_snapshots'] == 1 and result['total_diffs'] == 0
    assert repo.search_snapshots_and_diffs('Setbacks')['diffs'] == []
    with repo._connect() as conn:
        assert conn.execute('SELECT COUNT(*) FROM snapshots').fetchone()[0] == 3
        assert conn.execute('SELECT COUNT(*) FROM diffs').fetchone()[0] == 1
        assert conn.execute('SELECT cleaned_text FROM snapshots WHERE id=?', (bad['id'],)).fetchone()[0] == ''
    change_visibility(repo, applied, restore=True)
    result = repo.search_snapshots_and_diffs('')
    assert result['total_snapshots'] == 2 and result['total_diffs'] == 1
    with repo._connect() as conn:
        assert conn.execute('SELECT is_searchable FROM snapshots WHERE id=?', (unrelated['id'],)).fetchone()[0] == 0


def test_dependent_diff_stays_hidden_until_both_captures_restored(tmp_path):
    repo = Repository(db_path=str(tmp_path / 'visibility.db'))
    repo.supabase = None
    doc = repo.get_or_create_document('qa', 'Law', 'https://example.invalid')
    first = repo.create_snapshot(doc['id'], 1, '1', 'First', 'First')
    second = repo.create_snapshot(doc['id'], 2, '2', 'Second', 'Second')
    repo.save_diff(doc['id'], first['id'], second['id'], {})
    repo.set_capture_visibility([first['id'], second['id']], False, 'capture_audit:test')
    repo.set_capture_visibility([first['id']], True, 'capture_audit:test')
    assert repo.search_snapshots_and_diffs('')['total_diffs'] == 0
    repo.set_capture_visibility([second['id']], True, 'capture_audit:test')
    assert repo.search_snapshots_and_diffs('')['total_diffs'] == 1


def test_visibility_supabase_and_no_failure_fallback(tmp_path):
    repo = Repository(db_path=str(tmp_path / 'visibility.db'))
    repo.supabase = MagicMock()
    query = repo.supabase.table.return_value
    query.select.return_value.or_.return_value.execute.return_value.data = []
    snapshot_id = str(uuid.uuid4())
    query.update.return_value.in_.return_value.eq.return_value.execute.return_value.data = [{'id': snapshot_id}]
    assert repo.set_capture_visibility([snapshot_id], False, 'capture_audit:test')['snapshots'] == 1
    query.update.return_value.in_.return_value.eq.return_value.execute.side_effect = RuntimeError('database unavailable')
    with pytest.raises(RuntimeError):
        repo.set_capture_visibility([snapshot_id], False, 'capture_audit:test')


def test_visibility_schema_parity(tmp_path):
    repo = Repository(db_path=str(tmp_path / 'visibility.db'))
    sql = Path('db/migrations/009_capture_visibility.sql').read_text()
    with repo._connect() as conn:
        for table in ('snapshots', 'diffs'):
            columns = {row[1] for row in conn.execute(f'PRAGMA table_info({table})')}
            assert {'is_searchable', 'quality_reason'} <= columns
            assert f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS is_searchable BOOLEAN NOT NULL DEFAULT TRUE' in sql


def test_browser_search_skips_quarantined_latest_rows(local_browser):
    page, base, repo = local_browser
    doc = repo.get_or_create_document('qa', 'Usable official capture', 'https://example.invalid/law')
    repo.create_snapshot(doc['id'], 1, 'good', 'Section 1. Setbacks.', 'Section 1. Setbacks.')
    bad_ids = []
    for version in range(2, 34):
        bad_ids.append(repo.create_snapshot(doc['id'], version, str(version), '', '')['id'])
    repo.set_capture_visibility(bad_ids, False, 'capture_audit:browser')
    page.goto(base + '/')
    expect(page.locator('.result')).to_have_count(1)
    expect(page.locator('.result')).to_contain_text('Usable official capture')
    response = page.request.get(base + '/api/search?q=')
    assert response.json()['total_snapshots'] == 1
