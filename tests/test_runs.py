"""Tests for finder/runs.py — the daily batch report files."""

import json
import pytest

from finder import runs


@pytest.fixture
def runs_dir(tmp_path):
    original = runs.get_dir()
    runs.set_dir(tmp_path / "data" / "runs")
    yield runs.get_dir()
    runs.set_dir(original)


def _report(run_id: str, **kw) -> dict:
    base = {"run_id": run_id, "started_at": "2026-09-11T02:00:00",
            "finished_at": "2026-09-11T02:20:00", "ok": 2, "failed": 0,
            "articles": []}
    base.update(kw)
    return base


class TestRunIdValidation:
    @pytest.mark.parametrize("run_id", ["2026-09-11", "test_run", "a.b-c"])
    def test_valid(self, run_id):
        assert runs.is_valid_run_id(run_id) is True

    @pytest.mark.parametrize("run_id", ["", "../etc/passwd", "a/b", "..", "a b"])
    def test_invalid(self, run_id):
        assert runs.is_valid_run_id(run_id) is False

    def test_path_traversal_is_refused(self, runs_dir):
        with pytest.raises(ValueError):
            runs.report_path("../../etc/passwd")


class TestSaveLoad:
    def test_round_trip(self, runs_dir):
        runs.save_report(_report("2026-09-11", articles=[{"title": "A"}]))
        loaded = runs.load_report("2026-09-11")
        assert loaded["articles"][0]["title"] == "A"

    def test_directory_created(self, runs_dir):
        runs.save_report(_report("2026-09-11"))
        assert (runs_dir / "2026-09-11.json").exists()

    def test_missing_report_is_none(self, runs_dir):
        assert runs.load_report("2026-01-01") is None

    def test_save_is_atomic_no_tmp_left(self, runs_dir):
        runs.save_report(_report("2026-09-11"))
        assert list(runs_dir.glob("*.tmp")) == []

    def test_resave_overwrites(self, runs_dir):
        runs.save_report(_report("2026-09-11", ok=1))
        runs.save_report(_report("2026-09-11", ok=5))
        assert runs.load_report("2026-09-11")["ok"] == 5


class TestListing:
    def test_newest_first(self, runs_dir):
        for run_id in ["2026-09-09", "2026-09-11", "2026-09-10"]:
            runs.save_report(_report(run_id))
        assert [r["run_id"] for r in runs.list_runs()] == [
            "2026-09-11", "2026-09-10", "2026-09-09"]

    def test_empty_when_no_directory(self, runs_dir):
        assert runs.list_runs() == []

    def test_limit_respected(self, runs_dir):
        for i in range(5):
            runs.save_report(_report(f"2026-09-0{i}"))
        assert len(runs.list_runs(limit=2)) == 2

    def test_summary_never_carries_the_text(self, runs_dir):
        runs.save_report(_report("2026-09-11",
                                 articles=[{"title": "A", "text": "x" * 1000}]))
        assert "articles" not in runs.list_runs()[0]

    def test_corrupt_report_is_skipped_not_fatal(self, runs_dir):
        runs.save_report(_report("2026-09-11"))
        (runs_dir / "2026-09-10.json").write_text("{broken", encoding="utf-8")
        assert [r["run_id"] for r in runs.list_runs()] == ["2026-09-11"]

    def test_latest_run_id(self, runs_dir):
        assert runs.latest_run_id() is None
        runs.save_report(_report("2026-09-10"))
        runs.save_report(_report("2026-09-11"))
        assert runs.latest_run_id() == "2026-09-11"
