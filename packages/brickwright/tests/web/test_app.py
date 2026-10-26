from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from brickwright.web.app import create_app
from brickwright.web.preview import preview_ldraw


@pytest.fixture
def api(tmp_path: Path):
    with TestClient(create_app(tmp_path, generator_enabled=False)) as client:
        yield client


def test_session_history_and_ownership(api, tmp_path):
    created = api.post("/api/chats", json={}).json()
    assert api.get("/api/chats").json()[0]["id"] == created["id"]
    with TestClient(create_app(tmp_path, generator_enabled=False)) as other:
        assert other.get(f"/api/chats/{created['id']}").status_code == 404
    assert api.delete(f"/api/chats/{created['id']}").status_code == 204
    assert api.get("/api/chats").json() == []


def test_unavailable_generator_does_not_append_messages(api):
    chat = api.post("/api/chats", json={}).json()
    response = api.post(
        f"/api/chats/{chat['id']}/messages", json={"prompt": "a red car"}
    )
    assert response.status_code == 503
    assert api.get(f"/api/chats/{chat['id']}").json()["messages"] == []


def test_rejects_cross_origin_and_remote_hosts(api):
    assert (
        api.post(
            "/api/chats", json={}, headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert api.get("/api/chats", headers={"Host": "evil.example"}).status_code == 400


def test_bad_id_and_blank_prompt(api):
    assert api.get("/api/chats/not-an-id").status_code == 404
    chat = api.post("/api/chats", json={}).json()
    assert (
        api.post(
            f"/api/chats/{chat['id']}/messages", json={"prompt": "   "}
        ).status_code
        == 422
    )


def test_preview_has_real_meshes_and_bom():
    preview = preview_ldraw("1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat")
    assert preview["brick_count"] == 1
    assert preview["parts"][0]["quantity"] == 1
    assert len(preview["meshes"]["3001"]["vertices"]) > 8
    assert preview["instances"][0]["part"] == "3001"


def test_preview_preserves_lego_color():
    preview = preview_ldraw("1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat")
    assert preview["instances"][0]["color"] == [201, 26, 9]


def test_failed_generator_reports_error_without_a_fake_build(tmp_path, monkeypatch):
    import time

    executable = tmp_path / "fake-codex"
    executable.write_text("#!/bin/sh\ncat >/dev/null\nexit 1\n")
    executable.chmod(0o700)
    monkeypatch.setattr("brickwright.web.app.shutil.which", lambda _: str(executable))
    with TestClient(create_app(tmp_path / "data")) as client:
        chat = client.post("/api/chats").json()
        url = f"/api/chats/{chat['id']}"
        assert (
            client.post(url + "/messages", json={"prompt": "red pyramid"}).status_code
            == 202
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            chat = client.get(url).json()
            if chat["status"] == "error":
                break
            time.sleep(0.02)
        assert chat["status"] == "error"
        assert all(m["role"] == "user" for m in chat["messages"])
        assert client.get(url + "/builds/missing/model").status_code == 404


def test_stop_terminates_job_and_allows_another_message(tmp_path, monkeypatch):
    executable = tmp_path / "fake-codex"
    executable.write_text("#!/bin/sh\ncat >/dev/null\nsleep 30\n")
    executable.chmod(0o700)
    monkeypatch.setattr("brickwright.web.app.shutil.which", lambda _: str(executable))
    with TestClient(create_app(tmp_path / "data")) as client:
        chat = client.post("/api/chats").json()
        url = f"/api/chats/{chat['id']}"
        assert (
            client.post(url + "/messages", json={"prompt": "red pyramid"}).status_code
            == 202
        )
        assert (
            client.post(url + "/messages", json={"prompt": "another"}).status_code
            == 409
        )
        assert client.post(url + "/stop").json()["status"] == "cancelled"
        assert (
            client.post(url + "/messages", json={"prompt": "blue pyramid"}).status_code
            == 202
        )
        assert client.post(url + "/stop").json()["status"] == "cancelled"


def test_restart_recovers_interrupted_history(tmp_path):
    import json

    with TestClient(create_app(tmp_path, generator_enabled=False)) as client:
        chat = client.post("/api/chats").json()
        cookies = client.cookies
    path = next(tmp_path.glob("*/chats/*.json"))
    chat["status"] = "building"
    path.write_text(json.dumps(chat))
    with TestClient(create_app(tmp_path, generator_enabled=False)) as client:
        client.cookies.update(cookies)
        recovered = client.get(f"/api/chats/{chat['id']}").json()
        assert recovered["status"] == "error"
        assert "interrupted" in recovered["progress"]
