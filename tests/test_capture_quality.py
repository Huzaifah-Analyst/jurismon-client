from unittest.mock import MagicMock

import pytest
from db.repository import Repository
from extractor.capture_quality import capture_issue
from scripts.audit_capture_quality import audit


@pytest.mark.parametrize('url,text,reason', [
    ('https://example.invalid/law', '', 'empty_text'),
    ('https://www.gesetze-im-internet.de/aktuDienst.html', 'RSS updates', 'rss_catalogue'),
    ('https://open.canada.ca/data/en/dataset/abc.xml', 'DCAT metadata', 'dataset_metadata_or_resource_wrapper'),
    ('https://www.legislation.gov.au/C1914A00034', 'Save this title to My Account Set up an alert View document Select value', 'registry_wrapper'),
    ('https://www.legislation.gov.au/C1914A00034/text/law.html', 'Section 1. This Act applies to pensions.', None),
    ('https://laws-lois.justice.gc.ca/eng/acts/A-1/FullText.html', 'Section 1. Access to Information Act.', None),
])
def test_conservative_capture_classification(url, text, reason):
    assert capture_issue(url, text) == reason


def test_audit_preserves_sqlite_history(tmp_path):
    repo = Repository(db_path=str(tmp_path / 'audit.db'))
    repo.supabase = None
    doc = repo.get_or_create_document('quality-test', 'Law', 'https://example.invalid/law')
    old = repo.create_snapshot(doc['id'], 1, 'blank', '', '')
    repo.create_snapshot(doc['id'], 2, 'legal', 'Section 1', 'Section 1')
    result = audit(repo)
    assert result['checked'] == 2 and result['flagged'] == 1
    assert result['issues'][0]['id'] == old['id']
    assert repo.get_latest_snapshot(doc['id'])['version'] == 2
    assert repo.search_snapshots_and_diffs('')['total_snapshots'] == 2


def test_audit_supabase_reads_only(tmp_path):
    repo = Repository(db_path=str(tmp_path / 'audit.db'))
    repo.supabase = MagicMock()
    query = repo.supabase.table.return_value
    query.select.return_value.order.return_value.range.return_value.execute.return_value.data = [
        {'id': 'blank', 'document_id': 'doc', 'version': 1, 'cleaned_text': '', 'documents': [{'pdf_url': 'https://example.invalid/law'}]}
    ]
    assert audit(repo)['flagged'] == 1
    query.insert.assert_not_called()
    query.update.assert_not_called()
    query.delete.assert_not_called()
