from playwright.sync_api import expect
from tests.test_frontend_crawl_polling import local_browser


def test_typing_batches_requests_and_clear_cancels_timer(local_browser):
    page, base, _ = local_browser
    page.goto(base + '/')
    expect(page.locator('.skel-row')).to_have_count(0)
    requests = []
    page.on('request', lambda request: requests.append(request.url) if '/api/search?' in request.url else None)
    page.locator('#q').press_sequentially('parking', delay=40)
    with page.expect_response(lambda response: response.url.endswith('/api/search?q=parking')):
        page.wait_for_timeout(350)
    assert len(requests) == 1
    requests.clear()
    page.locator('#q').fill('zoning')
    page.locator('#q').press('Escape')
    expect(page.locator('#q')).to_have_value('')
    page.wait_for_timeout(450)
    assert len(requests) == 1
    assert requests[0].endswith('/api/search?q=')
