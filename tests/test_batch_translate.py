"""
Tests for batch_translate.py.

No network and no OpenAI: run_pipeline and fetch_wikitext are replaced, so
these check the batch's own behaviour — the report it builds, the queue
transitions it makes, and that one bad article does not stop the rest.
"""

import pytest

import batch_translate
from finder import runs, store
from webui import pipeline

LEAD = "'''Subject''' was a scholar of some note who taught for many years.\n\n"
LONG_ARTICLE = LEAD + (
    "== Biography ==\nBody paragraph.\n\n== References ==\n{{reflist}}\n"
    "[[Category:Scholars]]\n"
)


def _stats(**kw):
    base = {
        "counts": {"links": 3, "categories": 1, "templates": 1},
        "timings": {"total": 12.0},
        "input_size": 100,
        "output_size": 120,
        "cache": {},
        "translator": {},
        "reviewer": {"model": "gpt-5.4-mini"},
        "localization": {},
        "failed_titles": [],
        "label_mismatches": [],
    }
    base.update(kw)
    return base


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """An isolated queue and reports directory, seeded with two queued rows."""
    old_queue, old_runs = store.get_path(), runs.get_dir()
    store.set_path(tmp_path / "queue.json")
    runs.set_dir(tmp_path / "runs")

    data = store.load()
    store.upsert_article(data, "Small", size=2000, mode="full",
                         category="Category:X", url="http://example/Small")
    store.upsert_article(data, "Big", size=30000, mode="trim",
                         category="Category:X", url="http://example/Big")
    store.save(data)

    monkeypatch.setattr(batch_translate, "_fetch",
                        lambda title: (LONG_ARTICLE, title))
    monkeypatch.setattr(batch_translate.config, "ENABLE_REVIEW", True)

    yield tmp_path
    store.set_path(old_queue)
    runs.set_dir(old_runs)


@pytest.fixture
def ok_pipeline(monkeypatch):
    """run_pipeline that succeeds and records what it was handed."""
    calls = []

    def fake(raw_input, on_progress, *, article_title=None, review=None):
        calls.append({"input": raw_input, "title": article_title})
        return {"text": "tarjima qilingan matn", "title": article_title,
                "stats": _stats()}

    monkeypatch.setattr(pipeline, "run_pipeline", fake)
    return calls


class TestSuccessfulRun:
    def test_report_shape(self, workspace, ok_pipeline):
        code = batch_translate.main(["-n", "2", "--run-id", "test"])
        assert code == 0

        report = runs.load_report("test")
        assert report["requested"] == 2
        assert report["ok"] == 2 and report["failed"] == 0
        assert report["review_enabled"] is True
        assert report["finished_at"] is not None
        assert [a["title"] for a in report["articles"]] == ["Small", "Big"]

    def test_translated_text_is_stored_inline(self, workspace, ok_pipeline):
        batch_translate.main(["-n", "1", "--run-id", "test"])
        assert runs.load_report("test")["articles"][0]["text"] == "tarjima qilingan matn"

    def test_queue_rows_move_to_translated(self, workspace, ok_pipeline):
        batch_translate.main(["-n", "2", "--run-id", "test"])
        data = store.load()
        assert data["articles"]["Small"]["status"] == "translated"
        assert data["articles"]["Small"]["run_id"] == "test"
        assert data["stats"]["translated"] == 2
        assert data["stats"]["queued"] == 0

    def test_smallest_article_goes_first(self, workspace, ok_pipeline):
        batch_translate.main(["-n", "2", "--run-id", "test"])
        assert [c["title"] for c in ok_pipeline] == ["Small", "Big"]

    def test_title_is_passed_through_to_the_pipeline(self, workspace, ok_pipeline):
        batch_translate.main(["-n", "1", "--run-id", "test"])
        # Trimmed text cannot name its own article, so the caller must.
        assert ok_pipeline[0]["title"] == "Small"


class TestTrimming:
    def test_trim_mode_shortens_the_input(self, workspace, ok_pipeline):
        batch_translate.main(["--only", "Big", "--run-id", "test"])
        entry = runs.load_report("test")["articles"][0]
        assert entry["mode"] == "trim"
        assert entry["trim"]["trimmed"] is True
        assert "Body paragraph." not in ok_pipeline[0]["input"]
        assert entry["input_size"] < entry["original_size"]

    def test_full_mode_sends_the_whole_article(self, workspace, ok_pipeline):
        batch_translate.main(["--only", "Small", "--run-id", "test"])
        assert ok_pipeline[0]["input"] == LONG_ARTICLE
        assert runs.load_report("test")["articles"][0]["trim"] is None

    def test_untrimmable_article_falls_back_to_full(self, workspace, ok_pipeline, monkeypatch):
        monkeypatch.setattr(batch_translate, "_fetch", lambda t: (LEAD, t))
        batch_translate.main(["--only", "Big", "--run-id", "test"])
        entry = runs.load_report("test")["articles"][0]
        assert entry["mode"] == "full"
        assert entry["trim"]["reason"] == "no_sections"
        assert entry["status"] == "ok"


class TestFlags:
    def test_quality_flags_collected(self, workspace, monkeypatch):
        monkeypatch.setattr(pipeline, "run_pipeline",
                            lambda r, p, *, article_title=None, review=None: {
                                "text": "matn REF_a1b2c3d4 qoldi",
                                "title": article_title,
                                "stats": _stats(
                                    reviewer=None,
                                    failed_titles=["Some Title"],
                                    label_mismatches=[["Lohur", "Lahor"]],
                                ),
                            })
        batch_translate.main(["--only", "Small", "--run-id", "test"])
        flags = runs.load_report("test")["articles"][0]["flags"]
        assert flags["review_ran"] is False
        assert flags["failed_titles"] == ["Some Title"]
        assert flags["label_mismatches"] == [["Lohur", "Lahor"]]
        assert flags["leftover_refs"] == ["REF_a1b2c3d4"]

    def test_pipeline_warnings_are_captured(self, workspace, monkeypatch):
        from utils.logger import logger

        def noisy(raw_input, on_progress, *, article_title=None, review=None):
            logger.warning("3 havola inglizcha qoldi (label yoʻq, qoʻlda tekshiring)")
            return {"text": "matn", "title": article_title, "stats": _stats()}

        monkeypatch.setattr(pipeline, "run_pipeline", noisy)
        batch_translate.main(["--only", "Small", "--run-id", "test"])
        warnings = runs.load_report("test")["articles"][0]["flags"]["warnings"]
        assert any("inglizcha qoldi" in w for w in warnings)


class TestFailureHandling:
    def test_one_failure_does_not_stop_the_batch(self, workspace, monkeypatch):
        seen = []

        def flaky(raw_input, on_progress, *, article_title=None, review=None):
            seen.append(article_title)
            if article_title == "Small":
                raise pipeline.PipelineError("Tarjima muvaffaqiyatsiz tugadi")
            return {"text": "matn", "title": article_title, "stats": _stats()}

        monkeypatch.setattr(pipeline, "run_pipeline", flaky)
        code = batch_translate.main(["-n", "2", "--run-id", "test"])

        assert seen == ["Small", "Big"]
        report = runs.load_report("test")
        assert report["ok"] == 1 and report["failed"] == 1
        assert code == batch_translate.EXIT_ERROR

    def test_failed_article_is_marked_in_the_queue(self, workspace, monkeypatch):
        monkeypatch.setattr(pipeline, "run_pipeline",
                            lambda *a, **k: (_ for _ in ()).throw(
                                pipeline.PipelineError("bad")))
        batch_translate.main(["--only", "Small", "--run-id", "test"])
        rec = store.load()["articles"]["Small"]
        assert rec["status"] == "failed" and rec["error"] == "bad"

    def test_unexpected_exception_is_contained(self, workspace, monkeypatch):
        monkeypatch.setattr(pipeline, "run_pipeline",
                            lambda *a, **k: (_ for _ in ()).throw(ValueError("boom")))
        batch_translate.main(["--only", "Small", "--run-id", "test"])
        entry = runs.load_report("test")["articles"][0]
        assert entry["status"] == "failed"
        assert "boom" in entry["error"]
        assert "traceback" in entry

    def test_missing_article_is_recorded_not_raised(self, workspace, ok_pipeline, monkeypatch):
        monkeypatch.setattr(batch_translate, "_fetch", lambda t: (None, None))
        batch_translate.main(["--only", "Small", "--run-id", "test"])
        entry = runs.load_report("test")["articles"][0]
        assert entry["status"] == "failed"
        assert "topilmadi" in entry["error"]

    def test_report_written_after_every_article(self, workspace, monkeypatch):
        def crash_on_second(raw_input, on_progress, *, article_title=None, review=None):
            if article_title == "Big":
                raise KeyboardInterrupt
            return {"text": "matn", "title": article_title, "stats": _stats()}

        monkeypatch.setattr(pipeline, "run_pipeline", crash_on_second)
        with pytest.raises(KeyboardInterrupt):
            batch_translate.main(["-n", "2", "--run-id", "test"])

        # The first article was paid for in tokens; it must survive the crash.
        report = runs.load_report("test")
        assert report["ok"] == 1
        assert report["articles"][0]["title"] == "Small"
        assert report["finished_at"] is None


class TestCli:
    def test_empty_queue_is_not_an_error(self, workspace, ok_pipeline):
        data = store.load()
        for title in ("Small", "Big"):
            store.mark(data, title, "published")
        store.save(data)
        assert batch_translate.main(["-n", "2", "--run-id", "test"]) == 0
        assert runs.load_report("test") is None

    def test_dry_run_translates_nothing(self, workspace, ok_pipeline):
        assert batch_translate.main(["-n", "2", "--dry-run"]) == 0
        assert ok_pipeline == []
        assert runs.list_runs() == []

    def test_only_unknown_title_fails_cleanly(self, workspace, ok_pipeline):
        assert batch_translate.main(["--only", "Nope"]) == batch_translate.EXIT_ERROR
        assert ok_pipeline == []

    def test_invalid_run_id_refused(self, workspace, ok_pipeline):
        assert batch_translate.main(["--run-id", "../evil"]) == batch_translate.EXIT_ERROR
        assert ok_pipeline == []


class TestReviewGate:
    """
    Phase 5 must not follow webui/settings.json here.

    That switch belongs to the browser; a colleague turning review off in the
    UI must not silently disable it for an unattended batch run.
    """

    def test_config_default_is_used_not_the_browser_switch(self, workspace, ok_pipeline, monkeypatch):
        monkeypatch.setattr(batch_translate.config, "ENABLE_REVIEW", True)
        from webui import settings
        monkeypatch.setattr(settings, "get_review_enabled", lambda: False)
        batch_translate.main(["--only", "Small", "--run-id", "test"])
        assert runs.load_report("test")["review_enabled"] is True

    def test_no_review_flag_overrides_config(self, workspace, ok_pipeline, monkeypatch):
        monkeypatch.setattr(batch_translate.config, "ENABLE_REVIEW", True)
        batch_translate.main(["--only", "Small", "--run-id", "test", "--no-review"])
        assert runs.load_report("test")["review_enabled"] is False

    def test_review_flag_overrides_a_disabled_config(self, workspace, ok_pipeline, monkeypatch):
        monkeypatch.setattr(batch_translate.config, "ENABLE_REVIEW", False)
        batch_translate.main(["--only", "Small", "--run-id", "test", "--review"])
        assert runs.load_report("test")["review_enabled"] is True

    def test_gate_reaches_the_pipeline(self, workspace, monkeypatch):
        seen = {}

        def fake(raw_input, on_progress, *, article_title=None, review=None):
            seen["review"] = review
            return {"text": "matn", "title": article_title, "stats": _stats()}

        monkeypatch.setattr(pipeline, "run_pipeline", fake)
        batch_translate.main(["--only", "Small", "--run-id", "test", "--no-review"])
        assert seen["review"] is False

    def test_flags_cannot_be_combined(self, workspace, ok_pipeline):
        with pytest.raises(SystemExit):
            batch_translate.main(["--review", "--no-review"])
