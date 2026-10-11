"""Catalogue rejection and legal-text preservation regressions."""
from pathlib import Path
import pytest
from extractor.html_extractor import HTMLExtractor,NonDocumentPage
from api.main import format_result_items

@pytest.mark.parametrize("name,url",[("germany-rss.html","https://www.gesetze-im-internet.de/aktuDienst.html"),("canada-resource.html","https://open.canada.ca/data/en/dataset/4d277b82-c4af-4431-b31d-48fcece6dd8a/resource/93ca8728-3ee3-4156-8b41-4633e1cb688e")])
def test_real_portal_pages_are_not_legal_documents(name,url):
    html=(Path("tests/fixtures/extraction")/name).read_text(encoding="utf-8",errors="replace")
    with pytest.raises(NonDocumentPage):
        HTMLExtractor.extract_from_html(html,source_url=url)

@pytest.mark.parametrize("declaration",["",'<?xml version="1.0" encoding="UTF-8"?>'])
def test_statute_xml_keeps_title_sections_and_body(declaration):
    xml=declaration+'<act><metadata>Catalogue identifier</metadata><body><title>Zoning Act</title><prov><heading>Section 1</heading><para>Minimum setback is 25 feet.</para></prov></body></act>'
    cleaned,raw=HTMLExtractor.extract_from_html(xml)
    assert "Zoning Act" in cleaned and "Minimum setback is 25 feet." in cleaned
    assert "Catalogue identifier" not in cleaned

@pytest.mark.parametrize("root",["rss","feed","rdf"])
def test_xml_metadata_is_rejected(root):
    with pytest.raises(NonDocumentPage):
        HTMLExtractor.extract_from_html('<?xml version="1.0"?><'+root+'><title>Catalogue</title></'+root+'>')


def test_legal_article_header_and_custom_selector_are_preserved():
    html='<header>Site navigation</header><main><p>Other content</p><article id="law"><header>Section 1: Setbacks</header><p>Minimum setback is 25 feet.</p></article></main>'
    cleaned,raw=HTMLExtractor.extract_from_html(html,target_selector="#law")
    assert "Section 1: Setbacks" in cleaned
    assert "Site navigation" not in cleaned and "Other content" not in cleaned

@pytest.mark.parametrize("source",[{"name":"Germany - Gesetze im Internet"},[{"name":"Germany - Gesetze im Internet"}]])
def test_nested_source_relationship_has_real_name(source):
    items=format_result_items({"snapshots":[{"id":"qa","documents":{"title":"QA","pdf_url":"https://example.invalid","sources":source},"cleaned_text":"Section 1","crawled_at":"2026-10-11T00:00:00Z"}]})
    assert items[0]["entity"]=="Germany - Gesetze im Internet"


def test_crawler_skips_catalogue_and_empty_but_stores_legal_text(monkeypatch):
    import tempfile
    from types import SimpleNamespace
    from db.repository import Repository
    from scripts import run_crawler
    with tempfile.TemporaryDirectory() as directory:
        repository=Repository(db_path=str(Path(directory)/"ingestion.db"))
        source={"id":"qa-source","name":"QA source","base_url":"https://example.invalid","adapter_type":"custom","is_active":True}
        documents=[SimpleNamespace(url="https://example.invalid/"+name,title=name,document_type="html") for name in ["catalogue","empty","law"]]
        catalogue=Path("tests/fixtures/extraction/canada-resource.html").read_text(encoding="utf-8",errors="replace")
        bodies={documents[0].url:catalogue,documents[1].url:"",documents[2].url:'<main><h1>Section 1</h1><p>Minimum setback is 25 feet.</p></main>'}
        monkeypatch.setattr(run_crawler,"load_sites_config",lambda:[source])
        monkeypatch.setattr(run_crawler,"Repository",lambda:repository)
        monkeypatch.setattr(run_crawler,"get_adapter",lambda kind:SimpleNamespace(crawl=lambda config:SimpleNamespace(success=True,documents=documents)))
        monkeypatch.setattr(run_crawler.RequestsCrawler,"fetch_url",lambda self,url:SimpleNamespace(text=bodies[url],content=bodies[url].encode(),headers={}))
        monkeypatch.setattr(run_crawler,"send_crawl_report",lambda **kwargs:None)
        run_crawler.main()
        result=repository.search_snapshots_and_diffs("")
        assert len(result["snapshots"])==1
        assert result["snapshots"][0]["cleaned_text"]=="Section 1\nMinimum setback is 25 feet."
        run = repository.get_latest_crawl_run()
        assert run['status'] == 'failed' and run['sources_succeeded'] == 0
        assert run['sources_failed'] == 1


def test_real_au_registry_follows_embedded_law_and_rejects_wrapper():
    base="https://www.legislation.gov.au/C1914A00034"
    wrapper=Path("tests/fixtures/extraction/australia-act.html").read_text(encoding="utf-8",errors="replace")
    target=HTMLExtractor.embedded_document_url(wrapper,base)
    assert target=="https://www.legislation.gov.au/C1914A00034/asmade/1914-12-21/text/original/epub/OEBPS/document_1/document_1.html"
    with pytest.raises(NonDocumentPage):
        HTMLExtractor.extract_from_html(wrapper,source_url=base)
    document=Path("tests/fixtures/extraction/australia-document.html").read_text(encoding="utf-8",errors="replace")
    cleaned,raw=HTMLExtractor.extract_from_html(document,source_url=target)
    assert "War Pensions Act" in cleaned
    assert "Set up an alert" not in cleaned
    assert "Select value" not in cleaned
    assert len(cleaned)>1000


def test_embedded_document_cannot_point_to_a_different_host():
    with pytest.raises(NonDocumentPage):
        HTMLExtractor.embedded_document_url('<iframe id="epubFrame" src="https://example.invalid/text/law.html"></iframe>',"https://www.legislation.gov.au/C1914A00034")


def test_xhtml_still_strips_navigation_and_scripts():
    content='<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml"><body><nav>Navigation only</nav><main><h1>Section 1</h1><p>Minimum setback is 25 feet.</p><script>Tracking only</script></main></body></html>'
    cleaned,raw=HTMLExtractor.extract_from_html(content)
    assert "Section 1" in cleaned
    assert "Navigation only" not in cleaned and "Tracking only" not in cleaned


@pytest.mark.parametrize('url', ['https://example.invalid/law.pdf', 'https://example.invalid/document.cfm'])
def test_crawler_persists_actual_pdf_extraction(tmp_path, monkeypatch, url):
    import pymupdf
    from types import SimpleNamespace
    from db.repository import Repository
    from scripts import run_crawler
    repository = Repository(db_path=str(tmp_path / 'pdf.db'))
    repository.supabase = None
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72, 72), 'Section 1. Minimum setback shall be 25 feet in all residential districts.')
    content = pdf.tobytes()
    pdf.close()
    source = {'id': 'pdf-source', 'name': 'PDF QA', 'base_url': 'https://example.invalid', 'adapter_type': 'custom', 'is_active': True}
    document = SimpleNamespace(url=url, title='Setback Ordinance', document_type='pdf')
    monkeypatch.setattr(run_crawler, 'load_sites_config', lambda: [source])
    monkeypatch.setattr(run_crawler, 'Repository', lambda: repository)
    monkeypatch.setattr(run_crawler, 'get_adapter', lambda kind: SimpleNamespace(crawl=lambda config: SimpleNamespace(success=True, documents=[document])))
    monkeypatch.setattr(run_crawler.RequestsCrawler, 'fetch_pdf_bytes', lambda self, url: content)
    monkeypatch.setattr(run_crawler.RequestsCrawler, 'fetch_url', lambda self, url: SimpleNamespace(content=content, headers={'content-type': 'application/pdf'}))
    monkeypatch.setattr(run_crawler, 'send_crawl_report', lambda **kwargs: None)
    run_crawler.main()
    result = repository.search_snapshots_and_diffs('setback')
    assert len(result['snapshots']) == 1
    assert '25 feet' in result['snapshots'][0]['cleaned_text']
    assert repository.get_latest_crawl_run()['status'] == 'completed'
    # A successfully rechecked unchanged legal document is still a source success.
    run_crawler.main()
    assert repository.get_latest_crawl_run()['sources_succeeded'] == 1


def test_source_subset_crawl_rejects_unknown_and_skips_unselected(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from db.repository import Repository
    from scripts import run_crawler
    repo = Repository(db_path=str(tmp_path / 'subset.db'))
    repo.supabase = None
    sources = [{'id': value, 'name': value, 'adapter_type': 'custom', 'is_active': True} for value in ('selected', 'unselected')]
    calls = []
    monkeypatch.setattr(run_crawler, 'load_sites_config', lambda: sources)
    monkeypatch.setattr(run_crawler, 'Repository', lambda: repo)
    def crawl(config):
        calls.append(config['id'])
        return SimpleNamespace(success=True, documents=[])
    monkeypatch.setattr(run_crawler, 'get_adapter', lambda kind: SimpleNamespace(crawl=crawl))
    monkeypatch.setattr(run_crawler, 'send_crawl_report', lambda **kwargs: None)
    with pytest.raises(ValueError, match='Unknown source IDs'):
        run_crawler.main(source_ids=['missing'])
    assert not calls
    run_crawler.main(source_ids=['selected'])
    assert calls == ['selected']
    assert repo.get_latest_crawl_run()['total_sources'] == 1
    assert repo.get_latest_crawl_run()['status'] == 'failed'


def test_document_fetch_failure_is_not_reported_as_success(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from db.repository import Repository
    from scripts import run_crawler
    repo = Repository(db_path=str(tmp_path / 'failed-fetch.db'))
    repo.supabase = None
    source = {'id': 'failed-fetch', 'name': 'Failed fetch', 'adapter_type': 'custom', 'is_active': True}
    document = SimpleNamespace(url='https://example.invalid/law.pdf', title='Law', document_type='pdf')
    monkeypatch.setattr(run_crawler, 'load_sites_config', lambda: [source])
    monkeypatch.setattr(run_crawler, 'Repository', lambda: repo)
    monkeypatch.setattr(run_crawler, 'get_adapter', lambda kind: SimpleNamespace(crawl=lambda config: SimpleNamespace(success=True, documents=[document])))
    def fail(*args):
        raise RuntimeError('Official document fetch failed')
    monkeypatch.setattr(run_crawler.RequestsCrawler, 'fetch_pdf_bytes', fail)
    monkeypatch.setattr(run_crawler, 'send_crawl_report', lambda **kwargs: None)
    run_crawler.main()
    run = repo.get_latest_crawl_run()
    assert run['status'] == 'failed'
    assert run['sources_failed'] == 1 and run['sources_succeeded'] == 0
    assert repo.search_snapshots_and_diffs('')['total_snapshots'] == 0
