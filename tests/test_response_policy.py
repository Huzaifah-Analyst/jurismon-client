"""Cache privacy and negotiated compression against genuine API responses."""
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import api.main as main
from db.repository import Repository

@pytest.fixture
def policy_client(monkeypatch):
    with tempfile.TemporaryDirectory() as directory:
        repository=Repository(db_path=str(Path(directory)/"policy.db"))
        monkeypatch.setattr(main,"repo",repository)
        for index in range(20):
            repository.upsert_source({"id":str(index),"name":"Local policy test source "+str(index),"base_url":"https://example.invalid/"+str(index),"adapter_type":"custom"})
        yield TestClient(main.app)

@pytest.mark.parametrize("path",["/","/about","/admin","/account","/terms","/privacy"])
def test_html_revalidates_and_retains_etag(policy_client,path):
    response=policy_client.get(path)
    assert response.status_code==200
    assert response.headers["cache-control"]=="no-cache"
    assert "etag" in response.headers

@pytest.mark.parametrize("path,cache",[("/api/sources","public, max-age=60"),("/api/plans","no-cache"),("/api/search?q=","no-store"),("/api/admin/plans","no-store")])
def test_endpoint_specific_cache_policy(policy_client,path,cache):
    response=policy_client.get(path)
    assert response.headers["cache-control"]==cache
    assert "Authorization" in response.headers["vary"]


def test_authorization_never_uses_public_cache(policy_client):
    response=policy_client.get("/api/sources",headers={"Authorization":"Bearer invalid"})
    assert response.headers["cache-control"]=="no-store"


def test_gzip_negotiation_reduces_json_wire_size(policy_client,monkeypatch):
    import api.auth as auth
    monkeypatch.setattr(auth,"ADMIN_PASSWORD_HASH",auth.get_password_hash("policy-test-password"))
    login=policy_client.post("/api/admin/login",json={"email":auth.ADMIN_EMAIL,"password":"policy-test-password"})
    assert login.status_code==200
    token=login.json()["access_token"]
    identity=policy_client.get("/api/sources",headers={"Accept-Encoding":"identity","Authorization":"Bearer "+token})
    compressed=policy_client.get("/api/sources",headers={"Accept-Encoding":"gzip","Authorization":"Bearer "+token})
    assert "content-encoding" not in identity.headers
    assert compressed.headers["content-encoding"]=="gzip"
    assert compressed.json()==identity.json()
    assert int(compressed.headers["content-length"]) < len(identity.content)
    assert "Accept-Encoding" in compressed.headers["vary"]
    print("JSON wire bytes:", len(identity.content), "identity;", compressed.headers["content-length"], "gzip")


def test_small_json_does_not_get_compressed(policy_client):
    response=policy_client.get("/api/health",headers={"Accept-Encoding":"gzip"})
    assert "content-encoding" not in response.headers
