"""Configured repaired sources must discover official legal documents."""
import json
from pathlib import Path
from types import SimpleNamespace
from crawler.adapters.custom import CustomAdapter


def test_san_diego_discovers_amendments_without_navigation_or_forms():
    source = next(s for s in json.loads(Path('config/sites.json').read_text()) if s['id'] == 'site-07-sandiegocounty')
    html = Path('tests/fixtures/extraction/san-diego-code-updates.html').read_bytes()
    session = SimpleNamespace(fetch_page=lambda url: SimpleNamespace(content=html))
    documents = CustomAdapter(session).extract_documents(source)
    assert source['is_active'] is True
    assert len(documents) == 16
    assert any('Update 115.pdf' in d.url for d in documents)
    assert all('/zoning/' in d.url and d.url.endswith('.pdf') for d in documents)
    assert all('formfields' not in d.url and 'Suggestion' not in d.url for d in documents)
import pytest

@pytest.mark.parametrize('source_id,count,needle', [
    ('site-17-sbcounty', 21, 'ORD-No-4400-WEB.pdf'),
    ('site-09-miamidade', 12, 'suco2019.pdf'),
    ('site-13-austintexas', 20, 'document.cfm?id=478413'),
    ('site-05-hctx', 2, 'water_well_regs.pdf'),
    ('site-15-dallascounty', 2, 'Floodplain-Management-Regulations'),
    ('site-20-bexar', 1, '/DocumentCenter/View/7066/'),
    ('site-19-tarrantcounty', 2, 'DevelopmentRegulationsManual_SEPT2026.pdf'),
])
def test_repaired_listing_discovers_verified_legal_document(source_id, count, needle):
    source = next(s for s in json.loads(Path('config/sites.json').read_text()) if s['id'] == source_id)
    html = Path('tests/fixtures/extraction/' + source_id + '.html').read_bytes()
    documents = CustomAdapter(SimpleNamespace(fetch_page=lambda url: SimpleNamespace(content=html))).extract_documents(source)
    assert source['is_active'] is True
    assert len(documents) == count
    assert any(needle in d.url for d in documents)


@pytest.mark.parametrize('content_type', ['application/pdf;charset=UTF-8', 'application/octet-stream'])
def test_pdf_handler_ingests_legal_text_instead_of_binary_html(monkeypatch, tmp_path, content_type):
    import pymupdf
    from db.repository import Repository
    from scripts import run_crawler
    repository = Repository(db_path=str(tmp_path / 'handler.db'))
    source = {'id': 'handler-test', 'name': 'Isolated handler test', 'base_url': 'https://example.invalid', 'adapter_type': 'custom', 'is_active': True}
    document = SimpleNamespace(url='https://example.invalid/document.cfm?id=1', title='Handler legal text', document_type='ordinance')
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), 'Section 1: Legal test regulation. Minimum setback is 25 feet. This rule applies to all buildings.')
        body = pdf.tobytes()
    monkeypatch.setattr(run_crawler, 'load_sites_config', lambda: [source])
    monkeypatch.setattr(run_crawler, 'Repository', lambda: repository)
    monkeypatch.setattr(run_crawler, 'get_adapter', lambda kind: SimpleNamespace(crawl=lambda config: SimpleNamespace(success=True, documents=[document])))
    monkeypatch.setattr(run_crawler.RequestsCrawler, 'fetch_url', lambda self, url: SimpleNamespace(content=body, headers={'content-type': content_type}))
    monkeypatch.setattr(run_crawler, 'send_crawl_report', lambda **kwargs: None)
    run_crawler.main()
    snapshots = repository.search_snapshots_and_diffs('')['snapshots']
    assert len(snapshots) == 1
    assert 'Minimum setback is 25 feet.' in snapshots[0]['cleaned_text']
    assert '%PDF' not in snapshots[0]['cleaned_text']

def test_repaired_url_preserves_source_identity_and_updates_health(tmp_path):
    from db.repository import Repository
    repository = Repository(db_path=str(tmp_path / 'source-update.db'))
    original = {'id': 'moving-source', 'name': 'Moving source', 'base_url': 'https://example.invalid/old', 'is_active': False, 'health_status': 'dead_link', 'state': 'TX'}
    repository.upsert_source(original)
    document = repository.get_or_create_document(original['id'], 'Existing legal document', 'https://example.invalid/law.pdf')
    replacement = dict(original, base_url='https://example.invalid/new', is_active=True, health_status='operational', status_detail='Verified legal document')
    assert repository.upsert_source(replacement)['id'] == original['id']
    sources = [s for s in repository.get_all_sources() if s['id'] == original['id']]
    assert len(sources) == 1
    assert sources[0]['base_url'] == replacement['base_url']
    assert sources[0]['is_active'] == 1
    assert sources[0]['health_status'] == 'operational'
    with repository._connect() as connection:
        assert connection.execute('SELECT source_id FROM documents WHERE id=?', (document['id'],)).fetchone()[0] == original['id']
    repository.upsert_source({'id': original['id'], 'name': 'Updated name', 'base_url': replacement['base_url']})
    assert next(s for s in repository.get_all_sources() if s['id'] == original['id'])['state'] == 'TX'
