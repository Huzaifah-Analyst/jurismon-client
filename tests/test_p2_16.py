from unittest.mock import MagicMock
import json
from pathlib import Path
from playwright.sync_api import expect
from db.repository import Repository
from extractor.document_title import corrected_title, is_navigation_title
from scripts.repair_document_titles import repair
from test_frontend_crawl_polling import local_browser
from test_frontend_fixes import login_customer
from crawler.adapters.custom import CustomAdapter
from crawler.adapters.xml_feed import XmlFeedAdapter
from crawler.requests_crawler import RequestsCrawler


def test_ontario_adapter_excludes_pagers():
    session = MagicMock()
    session.fetch_page.return_value.content = b'<a href="/gazette?page=1">Page1</a><a href="/gazette/issue-159">Ontario Gazette Volume 159</a>'
    docs = CustomAdapter(session=session).extract_documents({'id':'ontario', 'base_url':'https://example.invalid/gazette', 'selectors_config':{'link_selector':'a'}})
    assert [d.title for d in docs] == ['Ontario Gazette Volume 159']


def test_atom_prefers_instrument_link_over_correction_slip():
    from bs4 import BeautifulSoup
    item = BeautifulSoup('<entry><link rel="related" href="/correction.pdf"/><link rel="alternate" href="/uksi/2026/123"/></entry>', 'xml').entry
    assert XmlFeedAdapter._link_of(item, 'link') == '/uksi/2026/123'


def test_document_timeout_is_configurable(monkeypatch):
    monkeypatch.setenv('CRAWLER_DOCUMENT_TIMEOUT_SECONDS', '45')
    assert RequestsCrawler().timeout == 45
    assert RequestsCrawler(timeout=7).timeout == 7


def test_large_document_has_own_scroll(local_browser):
    page, base, repo = local_browser
    login_customer(page, base, repo)
    repo.upsert_source({'id': 'large', 'name': 'Large document regression', 'base_url': 'https://example.invalid', 'adapter_type': 'custom'})
    doc = repo.get_or_create_document('large', 'Large statutory test document', 'https://example.invalid/large')
    text = 'Section 1. Statutory provisions.\n' * 17000
    repo.create_snapshot(doc['id'], 1, 'large', text, text)
    page.goto(base + '/')
    page.get_by_role('button', name='Show full page').first.click()
    box = page.locator('.result.is-open .full-box').first
    expect(box).to_be_visible()
    page.wait_for_timeout(500)
    dimensions = box.evaluate('(e) => ({height:e.getBoundingClientRect().height, max:innerHeight*.7, scroll:e.scrollHeight, client:e.clientHeight, overflow:getComputedStyle(e).overflowY})')
    assert dimensions['height'] <= dimensions['max'] + 1
    assert dimensions['scroll'] > dimensions['client']
    assert dimensions['overflow'] == 'auto'
    box.evaluate('(e) => e.scrollTop=500')
    assert box.evaluate('(e) => e.scrollTop') == 500
    evidence = Path('test-results/p2-16')
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / 'expanded-document-dom.json').write_text(json.dumps(dimensions, indent=2), encoding='utf-8')
    page.screenshot(path=str(evidence / 'expanded-document.png'), full_page=True)


def test_navigation_and_correction_titles():
    for label in ('Page1', 'Page9', 'Last pageLast »', 'Next', 'Previous', '4'):
        assert is_navigation_title(label)
    assert not is_navigation_title('Ontario Gazette Volume 159 Issue 4')
    assert corrected_title('Page1', 'Ontario Gazette') == 'Ontario Gazette capture, unlabeled'
    assert corrected_title('Correction Slip', 'UK', html='<h1>The Firearms (Amendment) Rules 2026</h1>') == 'The Firearms (Amendment) Rules 2026'
    assert corrected_title('Correction Slip', 'UK', text='Correction Slip\nRheoliadau Bwyd 2026\n1. Citation') == 'Rheoliadau Bwyd 2026'
    assert corrected_title('Correction Slip', 'UK', text='Rheoliadau Rheolaethau Swyddogol (Mewnforio Bwyd a\nBwyd Anifeiliaid) (Cymru) 2026\n1. Enwi') == 'Rheoliadau Rheolaethau Swyddogol (Mewnforio Bwyd a Bwyd Anifeiliaid) (Cymru) 2026'


def test_title_repair_preserves_snapshot(tmp_path):
    repo = Repository(db_path=str(tmp_path / 'titles.db'))
    repo.supabase = None
    repo.upsert_source({'id': 'ontario', 'name': 'Ontario Gazette', 'base_url': 'https://example.invalid', 'adapter_type': 'custom'})
    doc = repo.get_or_create_document('ontario', 'Page1', 'https://example.invalid/issue')
    snap = repo.create_snapshot(doc['id'], 1, 'a', 'Legal issue contents', 'Legal issue contents')
    assert repair(repo)[0]['applied'] is False
    assert repair(repo, True)[0]['applied'] is True
    assert repair(repo, True) == []
    assert repo.get_latest_snapshot(doc['id'])['id'] == snap['id']


def test_title_compare_and_set_supabase(tmp_path):
    repo = Repository(db_path=str(tmp_path / 'supabase.db'))
    repo.supabase = MagicMock()
    query = repo.supabase.table.return_value
    query.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = [{'id':'doc'}]
    assert repo.correct_document_title('doc', 'Page1', 'Ontario Gazette capture, unlabeled')
    query.update.assert_called_once_with({'title': 'Ontario Gazette capture, unlabeled'})
