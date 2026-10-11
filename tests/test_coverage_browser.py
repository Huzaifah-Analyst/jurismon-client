from playwright.sync_api import expect
from tests.test_frontend_crawl_polling import local_browser


def test_coverage_distinguishes_health_from_capture(local_browser):
    page, base, repository = local_browser
    repository.upsert_source({'id': 'coverage-local', 'name': 'Local QA', 'base_url': 'https://example.invalid', 'adapter_type': 'custom', 'health_status': 'operational'})
    repository.upsert_source({'id': 'coverage-blocked', 'name': 'Blocked QA', 'base_url': 'https://example.invalid/blocked', 'adapter_type': 'custom', 'health_status': 'cloudflare_blocked'})
    sources = repository.get_all_sources()
    operational = sum(source.get('health_status') == 'operational' for source in sources)
    page.goto(base + '/')
    expect(page.locator('#title')).to_contain_text(f'{operational} sources marked operational, {len(sources)} configured')
    page.get_by_role('link', name='Coverage and exclusions').click()
    expect(page.locator('#coverage')).to_contain_text('do not prove that a recent crawl stored usable legal text')
    expect(page.locator('#coverage')).to_contain_text('Capture dates are not legal effective dates')
    expect(page.locator('#coverage')).to_contain_text('are not bypassed')
