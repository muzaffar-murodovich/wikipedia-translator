"""
Route tests for the web UI's Kunlik page.

Skipped when Flask is absent: it lives in webui/requirements.txt, not in the
project's own requirements, so the suite must still run without it.
"""

import pytest

pytest.importorskip("flask", reason="Flask webui/requirements.txt da, majburiy emas")

from finder import runs, store  # noqa: E402
from webui.app import app  # noqa: E402


@pytest.fixture
def client(tmp_path):
    old_queue, old_runs = store.get_path(), runs.get_dir()
    store.set_path(tmp_path / "queue.json")
    runs.set_dir(tmp_path / "runs")

    data = store.load()
    store.upsert_article(data, "Sulayman al-Ghazzi", size=6783, mode="full")
    store.mark(data, "Sulayman al-Ghazzi", "translated")
    store.save(data)

    runs.save_report({
        "run_id": "2026-09-11",
        "started_at": "2026-09-11T02:00:00",
        "finished_at": "2026-09-11T02:20:00",
        "review_enabled": True,
        "requested": 1, "ok": 1, "failed": 0,
        "articles": [{
            "title": "Sulayman al-Ghazzi",
            "url": "https://en.wikipedia.org/wiki/Sulayman_al-Ghazzi",
            "mode": "full", "status": "ok",
            "original_size": 6783, "input_size": 6783, "output_size": 6500,
            "trim": None,
            "flags": {"review_ran": True, "failed_titles": [],
                      "label_mismatches": [], "leftover_refs": [], "warnings": []},
            "text": "'''Sulaymon al-Gʻazziy''' — shoir.",
        }],
    })

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

    store.set_path(old_queue)
    runs.set_dir(old_runs)


class TestPage:
    def test_page_renders(self, client):
        resp = client.get("/kunlik")
        assert resp.status_code == 200
        assert b"kunlik.js" in resp.data


class TestRunsListing:
    def test_lists_runs(self, client):
        rows = client.get("/api/runs").get_json()
        assert rows[0]["run_id"] == "2026-09-11"
        assert rows[0]["ok"] == 1

    def test_listing_omits_the_text(self, client):
        assert "articles" not in client.get("/api/runs").get_json()[0]


class TestRunReport:
    def test_report_carries_the_text(self, client):
        data = client.get("/api/run/2026-09-11").get_json()
        assert data["articles"][0]["text"].startswith("'''Sulaymon")

    def test_latest_alias(self, client):
        assert client.get("/api/run/latest").get_json()["run_id"] == "2026-09-11"

    def test_published_is_joined_from_the_queue(self, client):
        data = client.get("/api/run/2026-09-11").get_json()
        assert data["articles"][0]["published"] is False

        client.post("/api/publish", json={"title": "Sulayman al-Ghazzi",
                                          "published": True})
        data = client.get("/api/run/2026-09-11").get_json()
        assert data["articles"][0]["published"] is True

    def test_unknown_run(self, client):
        assert client.get("/api/run/2026-01-01").status_code == 404

    @pytest.mark.parametrize("run_id", ["..%2F..%2Fetc%2Fpasswd", "a%2Fb"])
    def test_path_traversal_refused(self, client, run_id):
        assert client.get(f"/api/run/{run_id}").status_code in (400, 404)

    def test_latest_with_no_runs(self, client, tmp_path):
        runs.set_dir(tmp_path / "empty")
        assert client.get("/api/run/latest").status_code == 404


class TestPublish:
    def test_marks_published_in_the_queue(self, client):
        resp = client.post("/api/publish", json={"title": "Sulayman al-Ghazzi",
                                                 "published": True})
        assert resp.get_json() == {"status": "ok", "published": True}
        rec = store.load()["articles"]["Sulayman al-Ghazzi"]
        assert rec["status"] == "published"
        assert rec["published_at"] is not None

    def test_unticking_returns_it_to_translated(self, client):
        client.post("/api/publish", json={"title": "Sulayman al-Ghazzi",
                                          "published": True})
        client.post("/api/publish", json={"title": "Sulayman al-Ghazzi",
                                          "published": False})
        assert store.load()["articles"]["Sulayman al-Ghazzi"]["status"] == "translated"

    def test_unknown_title(self, client):
        resp = client.post("/api/publish", json={"title": "Nope", "published": True})
        assert resp.status_code == 404

    def test_missing_title(self, client):
        assert client.post("/api/publish", json={}).status_code == 400
