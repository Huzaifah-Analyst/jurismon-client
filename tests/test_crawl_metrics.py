from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from db.repository import Repository
from playwright.sync_api import expect
from tests.test_frontend_crawl_polling import local_browser, admin_browser


def test_sqlite_metrics_use_runs_not_source_timestamps(tmp_path):
    repo = Repository(db_path=str(tmp_path / 'metrics.db'))
    repo.supabase = None
    assert repo.get_crawl_run_metrics()['started_today'] == 0
    yesterday = repo.start_crawl_run()
    repo.finish_crawl_run(yesterday, 'failed')
    with repo._connect() as conn:
        conn.execute('UPDATE crawl_runs SET started_at=? WHERE id=?',
                     ((datetime.now(timezone.utc) - timedelta(days=1)).isoformat(), yesterday))
        conn.commit()
    completed = repo.start_crawl_run()
    repo.finish_crawl_run(completed, 'completed')
    failed = repo.start_crawl_run()
    repo.finish_crawl_run(failed, 'partial_failure')
    running = repo.start_crawl_run()
    metrics = repo.get_crawl_run_metrics()
    assert metrics['started_today'] == 3
    assert metrics['failed_today'] == 1
    assert metrics['running_today'] == 1
    assert metrics['latest']['id'] == running


def test_supabase_metrics_and_failure_not_masked(tmp_path):
    repo = Repository(db_path=str(tmp_path / 'metrics.db'))
    repo.supabase = MagicMock()
    query = repo.supabase.table.return_value
    query.select.return_value.gte.return_value.execute.return_value.data = [{'id': 'real', 'status': 'completed'}]
    query.select.return_value.order.return_value.limit.return_value.execute.return_value.data = [{'id': 'real', 'status': 'completed'}]
    assert repo.get_crawl_run_metrics()['started_today'] == 1
    query.select.return_value.gte.assert_called_once()
    query.select.return_value.gte.return_value.execute.side_effect = RuntimeError('offline')
    with pytest.raises(RuntimeError):
        repo.get_crawl_run_metrics()


def test_dashboard_real_counts_and_polling(admin_browser):
    page, base, repo = admin_browser
    run = repo.start_crawl_run()
    page.goto(base + '/admin')
    expect(page.locator('#k-runs')).to_have_text('1')
    expect(page.locator('#run-meta')).to_contain_text('(running)')
    repo.finish_crawl_run(run, 'completed', total_sources=2, sources_succeeded=2)
    expect(page.locator('#run-meta')).to_contain_text('completed', timeout=12000)
    expect(page.locator('#k-runs-foot')).to_contain_text('0 running')
