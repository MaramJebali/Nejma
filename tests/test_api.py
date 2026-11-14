# AI-generated code: written with Claude (Anthropic) at the team's direction for NASA Space Apps 2026.
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

import api.main as service  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    """The service with the slow archive work replaced by an instant answer."""

    def instant(job, text, fov, band):
        job.update(state="done", message="Done.", target={"query": text}, view={"band": band}, finished=0.0)

    monkeypatch.setattr(service, "run", instant)
    monkeypatch.setattr(service.time, "time", lambda: 1.0)  # keeps finished jobs from being forgotten mid-test
    service.JOBS.clear()
    return TestClient(service.app)


def test_bad_requests_are_refused(client):
    assert client.get("/view", params={"q": "  "}).status_code == 400
    assert client.get("/view", params={"q": "R Dra", "band": 9}).status_code == 400
    assert client.get("/job/unknown").status_code == 404


def test_a_question_is_answered_and_bookkeeping_stays_private(client):
    started = client.get("/view", params={"q": "R Dra", "fov": 0.11, "band": 2}).json()
    assert "key" not in started and "finished" not in started
    answer = client.get(f"/job/{started['id']}").json()
    assert answer["state"] == "done" and answer["target"] == {"query": "R Dra"} and answer["view"] == {"band": 2}


def test_the_same_question_is_not_fetched_twice(client):
    first = client.get("/view", params={"q": "R Dra", "band": 2}).json()
    again = client.get("/view", params={"q": " r dra ", "band": 2}).json()
    other = client.get("/view", params={"q": "R Dra", "band": 3}).json()
    assert again["id"] == first["id"] and other["id"] != first["id"]


def test_too_many_at_once_are_turned_away(client, monkeypatch):
    monkeypatch.setattr(service, "run", lambda job, text, fov, band: None)  # these never finish
    for i in range(service.MAX_RUNNING):
        assert client.get("/view", params={"q": f"star {i}"}).status_code == 200
    assert client.get("/view", params={"q": "one more"}).status_code == 429
