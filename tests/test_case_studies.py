import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import expect
import api.main as main
from db.repository import Repository
from tests.test_frontend_crawl_polling import local_browser


def seed_case(repo):
    case = json.loads(Path('config/case_studies.json').read_text())[0]
    doc = repo.get_or_create_document(case['source_id'], 'Official rule', case['official_url'])
    capture = repo.create_snapshot(doc['id'], 1, 'hash', '4.4.9 Preservation Bonus', '4.4.9 Preservation Bonus')
    return case, capture


def test_cases_require_real_visible_supporting_capture(tmp_path, monkeypatch):
    repo = Repository(db_path=str(tmp_path / 'cases.db'))
    repo.supabase = None
    monkeypatch.setattr(main, 'repo', repo)
    client = TestClient(main.app)
    assert client.get('/api/case-studies').json()['cases'] == []
    case, capture = seed_case(repo)
    response = client.get('/api/case-studies')
    assert response.status_code == 200
    published = response.json()['cases']
    assert len(published) == 1 and published[0]['capture']['id'] == capture['id']
    assert 'cleaned_text' not in json.dumps(published)
    assert 'required_terms' not in published[0]
    repo.set_capture_visibility([capture['id']], False, 'review')
    assert client.get('/api/case-studies').json()['cases'] == []
    assert client.get('/case-studies').status_code == 200
    assert 'JurisMon Terms' in client.get('/terms').text
    assert '/case-studies' in client.get('/sitemap.xml').text


def test_case_evidence_rejects_missing_terms_and_surfaces_storage_failure(tmp_path, monkeypatch):
    repo = Repository(db_path=str(tmp_path / 'cases.db'))
    repo.supabase = None
    case, _ = seed_case(repo)
    assert repo.get_case_study_capture(case['source_id'], case['official_url'], ['missing legal section']) is None
    repo.supabase = MagicMock()
    repo.supabase.table.side_effect = RuntimeError('Evidence storage unavailable')
    monkeypatch.setattr(main, 'repo', repo)
    response = TestClient(main.app).get('/api/case-studies')
    assert response.status_code == 503
    assert response.json()['detail'] == 'Case-study evidence is temporarily unavailable.'


def test_supabase_case_evidence_returns_metadata_only(tmp_path):
    repo = Repository(db_path=str(tmp_path / 'cases.db'))
    client = MagicMock()
    repo.supabase = client
    doc_query, capture_query = MagicMock(), MagicMock()
    client.table.side_effect = [doc_query, capture_query]
    doc_query.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [{'id': 'doc'}]
    capture_query.select.return_value.in_.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [{'id': 'snap', 'version': 2, 'crawled_at': '2026-10-11T00:00:00Z', 'cleaned_text': '4.4.9 Preservation Bonus'}]
    assert repo.get_case_study_capture('source', 'https://example.invalid', ['4.4.9']) == {'id': 'snap', 'version': 2, 'crawled_at': '2026-10-11T00:00:00Z'}
    capture_query.select.return_value.in_.return_value.eq.assert_called_once_with('is_searchable', True)


@pytest.mark.parametrize('mode', ['light', 'dark'])
def test_case_page_actual_evidence_and_search_link(local_browser, mode):
    page, base, repo = local_browser
    page.emulate_media(color_scheme=mode)
    page.set_viewport_size({'width': 375, 'height': 812})
    page.goto(base + '/case-studies')
    expect(page.locator('#status')).to_contain_text('No case studies')
    seed_case(repo)
    page.reload()
    expect(page.locator('article')).to_have_count(1)
    expect(page.locator('article')).to_contain_text('Stored version 1')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.add_script_tag(path='tests/vendor/axe-core-4.10.3.min.js')
    axe = page.evaluate('async () => await axe.run(document)')
    assert not axe['violations'], [v['id'] for v in axe['violations']]
    page.get_by_role('link', name='Search captured text').click()
    expect(page.locator('#q')).to_have_value('Preservation Bonus')
    expect(page.locator('.skel-row')).to_have_count(0)


def test_public_coverage_lists_actual_inactive_sources(local_browser):
    page, base, repo = local_browser
    expected = [s for s in repo.get_all_sources() if not s.get('is_active')]
    response = page.request.get(base + '/api/sources').json()
    assert 'sources' not in response
    assert all(set(item) == {'name', 'health_status'} for item in response['exclusions'])
    page.goto(base + '/about#coverage')
    expect(page.locator('#excluded-sources li')).to_have_count(len(expected))
    for source in expected:
        expect(page.locator('#excluded-sources')).to_contain_text(source['name'])
