"""Configured trial activation against isolated real SQLite state."""
import copy
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
import api.main as main
from db.repository import Repository


@pytest.fixture
def configured_app(monkeypatch):
    with tempfile.TemporaryDirectory() as directory:
        repository = Repository(db_path=str(Path(directory) / "trial.db"))
        monkeypatch.setattr(main, "repo", repository)
        catalogue = copy.deepcopy(main.get_plan_catalogue())
        monkeypatch.setattr(main, "get_plan_catalogue", lambda: copy.deepcopy(catalogue))
        emails = []
        monkeypatch.setattr(main.mailer, "send", lambda **message: emails.append(message) or True)
        yield TestClient(main.app), repository, catalogue, emails


@pytest.mark.parametrize("days", [14, 34, 67, 0])
@pytest.mark.parametrize("activation", ["verify", "reset"])
def test_configured_trial_grant_and_email(configured_app, days, activation):
    client, repository, catalogue, emails = configured_app
    catalogue["trial_days"] = days
    email = "trial@example.invalid"
    result = client.post("/api/auth/register", json={"email": email, "password": "TrialPassword123"})
    assert result.status_code == 200
    assert repository.get_user_by_email(email)["trial_ends_at"] is None
    copy_text = f"{days}-day free trial" if days else "Subscribe for full access"
    assert copy_text in emails[-1]["html"]
    assert copy_text in emails[-1]["text"]
    assert client.post("/api/auth/resend-code", json={"email": email}).status_code == 200
    assert copy_text in emails[-1]["html"]
    code = repository.get_user_by_email(email)["verification_code"]
    before = datetime.now(timezone.utc)
    if activation == "verify":
        result = client.post("/api/auth/verify-code", json={"email": email, "code": code})
    else:
        result = client.post("/api/auth/reset-password", json={"email": email, "code": code, "new_password": "ChangedPassword123"})
    assert result.status_code == 200
    user = repository.get_user_by_email(email)
    ends = datetime.fromisoformat(user["trial_ends_at"])
    assert before + timedelta(days=days) <= ends <= datetime.now(timezone.utc) + timedelta(days=days)
    assert repository.get_user_access_status(user["id"])["has_access"] is (days > 0)
    catalogue["trial_days"] = 45
    assert client.post("/api/auth/verify-code", json={"email": email, "code": code}).status_code == 200
    assert repository.get_user_by_email(email)["trial_ends_at"] == user["trial_ends_at"]


def test_duration_is_read_when_verification_happens(configured_app):
    client, repository, catalogue, emails = configured_app
    catalogue["trial_days"] = 14
    email = "changed@example.invalid"
    assert client.post("/api/auth/register", json={"email": email, "password": "TrialPassword123"}).status_code == 200
    catalogue["trial_days"] = 34
    code = repository.get_user_by_email(email)["verification_code"]
    assert client.post("/api/auth/verify-code", json={"email": email, "code": code}).status_code == 200
    ends = datetime.fromisoformat(repository.get_user_by_email(email)["trial_ends_at"])
    assert 33.99 < (ends - datetime.now(timezone.utc)).total_seconds() / 86400 <= 34


def test_admin_setting_reaches_public_offer_and_trial(configured_app, monkeypatch):
    import json
    import api.auth as auth
    client, repository, catalogue, emails = configured_app
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / "plans.json"
        def isolated_write(value):
            target.write_text(json.dumps(value), encoding="utf-8")
            catalogue.clear()
            catalogue.update(json.loads(target.read_text(encoding="utf-8")))
        monkeypatch.setattr(main, "_write_plan_catalogue", isolated_write)
        monkeypatch.setattr(auth, "ADMIN_PASSWORD_HASH", auth.get_password_hash("LocalAdminPassword123"))
        login = client.post("/api/admin/login", json={"email": main.ADMIN_EMAIL, "password": "LocalAdminPassword123"})
        assert login.status_code == 200
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        updated = client.patch("/api/admin/plans", json={"trial_days": 34}, headers=headers)
        assert updated.status_code == 200
        assert updated.json()["changes_recorded"]
        assert client.get("/api/plans").json()["trial_days"] == 34
        assert json.loads(target.read_text())["trial_days"] == 34
        email = "admin-change@example.invalid"
        assert client.post("/api/auth/register", json={"email": email, "password": "TrialPassword123"}).status_code == 200
        assert "34-day free trial" in emails[-1]["html"]
        code = repository.get_user_by_email(email)["verification_code"]
        assert client.post("/api/auth/verify-code", json={"email": email, "code": code}).status_code == 200
        ends = datetime.fromisoformat(repository.get_user_by_email(email)["trial_ends_at"])
        assert 33.99 < (ends - datetime.now(timezone.utc)).total_seconds() / 86400 <= 34
