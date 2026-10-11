"""A slow synchronous database read must not stall unrelated API requests."""
import asyncio
import threading
from pathlib import Path
import httpx
import api.main as main
from db.repository import Repository


def test_slow_search_does_not_block_health(monkeypatch, tmp_path):
    repository = Repository(db_path=str(tmp_path / 'search.db'))
    monkeypatch.setattr(main, 'repo', repository)
    entered = threading.Event()
    release = threading.Event()
    original = repository.search_snapshots_and_diffs

    def slow_read(*args, **kwargs):
        entered.set()
        if not release.wait(3):
            raise TimeoutError('Search blocked the independent health request')
        return original(*args, **kwargs)

    monkeypatch.setattr(repository, 'search_snapshots_and_diffs', slow_read)

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://test') as client:
            search = asyncio.create_task(client.get('/api/search?q=parking'))
            try:
                assert await asyncio.to_thread(entered.wait, 2)
                response = await asyncio.wait_for(client.get('/api/health'), timeout=1)
                assert response.status_code == 200
                assert not search.done()
            finally:
                release.set()
            response = await search
            assert response.status_code == 200
            assert response.json()['query'] == 'parking'
            assert response.json()['is_gated'] is True
            assert response.json()['items'] == []

    asyncio.run(exercise())

from test_frontend_crawl_polling import local_browser


def test_browser_health_responds_while_search_is_waiting(local_browser, monkeypatch):
    import json
    page, base, repository = local_browser
    entered = threading.Event()
    release = threading.Event()
    completed = threading.Event()
    original = repository.search_snapshots_and_diffs

    def delayed_read(*args, **kwargs):
        entered.set()
        if not release.wait(10):
            raise TimeoutError('Browser health request did not release search')
        result = original(*args, **kwargs)
        completed.set()
        return result

    monkeypatch.setattr(repository, 'search_snapshots_and_diffs', delayed_read)
    try:
        page.goto(base + '/', wait_until='domcontentloaded')
        assert entered.wait(5)
        health_page = page.context.browser.new_page()
        response = health_page.goto(base + '/api/health', wait_until='domcontentloaded', timeout=3000)
        assert response.status == 200
        assert json.loads(health_page.locator('body').inner_text())['status'] == 'ok'
        assert not completed.is_set()
    finally:
        release.set()
    assert completed.wait(5)
