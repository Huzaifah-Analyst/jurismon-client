from unittest.mock import MagicMock
import pytest
from db.repository import Repository


@pytest.mark.parametrize('method,args', [
    ('upsert_source', ({'id': 'qa', 'name': 'QA', 'base_url': 'https://example.invalid'},)),
    ('get_or_create_document', ('qa', 'Law', 'https://example.invalid/law')),
    ('get_latest_snapshot', ('document-id',)),
    ('create_snapshot', ('document-id', 1, 'hash', 'Raw law', 'Clean law')),
    ('save_diff', ('document-id', None, 'snapshot-id', {})),
])
def test_production_ingestion_error_does_not_write_to_local_database(tmp_path, method, args):
    repo = Repository(db_path=str(tmp_path / 'storage.db'))
    repo.supabase = MagicMock()
    repo.supabase.table.side_effect = RuntimeError('Production storage unavailable')
    repo._connect = MagicMock(side_effect=AssertionError('SQLite must not be used'))
    with pytest.raises(RuntimeError, match='Production storage unavailable'):
        getattr(repo, method)(*args)
    repo._connect.assert_not_called()
