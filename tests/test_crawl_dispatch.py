import asyncio
import subprocess
from unittest.mock import MagicMock

import pytest
from fastapi import BackgroundTasks
import api.main as main
from db.repository import Repository


@pytest.mark.parametrize('failure', [None, subprocess.CalledProcessError(1, 'sudo'), subprocess.TimeoutExpired('sudo', 10)])
def test_dispatch_checks_systemd_result_and_falls_back(tmp_path, monkeypatch, failure):
    repo = Repository(db_path=str(tmp_path / 'dispatch.db'))
    repo.supabase = None
    monkeypatch.setattr(main, 'repo', repo)
    monkeypatch.setattr(main, '_systemd_crawl_available', lambda: True)
    process = MagicMock(side_effect=failure, return_value=subprocess.CompletedProcess([], 0))
    monkeypatch.setattr(main.subprocess, 'run', process)
    background = BackgroundTasks()
    result = asyncio.run(main.trigger_admin_crawl(background, admin={'sub': 'isolated-admin'}))
    kwargs = process.call_args.kwargs
    assert kwargs['check'] is True and kwargs['timeout'] == 10
    assert '--no-block' in process.call_args.args[0]
    assert repo.get_latest_crawl_run()['id'] == result['crawl_run_id']
    if failure:
        assert len(background.tasks) == 1
        assert background.tasks[0].args == (result['crawl_run_id'],)
        assert 'fallback' in result['message']
    else:
        assert not background.tasks
