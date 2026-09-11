"""
Tests for finder/cli.py.

These assert exact stdout lines on purpose: that format is the contract the
discovery agent is written against, and a silent change to it would break
the agent without failing any other test.
"""

import json
import logging

import pytest

from finder import cli, store, wiki


@pytest.fixture(autouse=True)
def restore_log_level():
    """
    cli.main() silences the pipeline logger for the whole process.

    That is right for a CLI run - stdout is the agent's contract - but it
    would otherwise leak into every test that asserts on log output.
    """
    log = logging.getLogger("WikiTranslator")
    level = log.level
    yield
    log.setLevel(level)


@pytest.fixture
def queue(tmp_path):
    original = store.get_path()
    store.set_path(tmp_path / "data" / "queue.json")
    yield store.get_path()
    store.set_path(original)


def run(capsys, *argv):
    """Run the CLI and return (exit_code, [stdout lines])."""
    code = cli.main(list(argv))
    out = capsys.readouterr().out.splitlines()
    return code, out


@pytest.fixture
def members(monkeypatch):
    def set_members(mapping):
        monkeypatch.setattr(wiki, "fetch_category_members", lambda c: mapping)
    return set_members


@pytest.fixture
def titles(monkeypatch):
    def set_titles(mapping):
        monkeypatch.setattr(wiki, "fetch_titles_info", lambda t: mapping)
    return set_titles


class TestCatList:
    def test_header_counts_and_rows(self, capsys, queue, members):
        members({
            "Small": {"uz": None, "size": 5296},
            "Big": {"uz": None, "size": 18432},
            "Done": {"uz": "Bor", "size": 1000},
        })
        code, out = run(capsys, "cat-list", "Hadith scholars")
        assert code == 0
        assert out[0] == ("CATEGORY Category:Hadith scholars members=3 "
                          "missing=2 new=2 known=0")
        assert out[1] == "5296\tfull\tSmall"
        assert out[2] == "18432\ttrim\tBig"
        assert out[-1] == "END"

    def test_threshold_decides_mode(self, capsys, queue, members, monkeypatch):
        monkeypatch.setattr(cli.config, "TRIM_SIZE_THRESHOLD", 10000)
        members({"Edge": {"uz": None, "size": 10000},
                 "Over": {"uz": None, "size": 10001}})
        _, out = run(capsys, "cat-list", "X")
        assert "10000\tfull\tEdge" in out
        assert "10001\ttrim\tOver" in out

    def test_known_titles_are_not_offered_again(self, capsys, queue, members):
        data = store.load()
        store.upsert_article(data, "Seen", status="rejected")
        store.save(data)
        members({"Seen": {"uz": None, "size": 100},
                 "Fresh": {"uz": None, "size": 200}})
        _, out = run(capsys, "cat-list", "X")
        assert "new=1 known=1" in out[0]
        assert not any("Seen" in line for line in out[1:])

    def test_category_recorded_as_in_progress(self, capsys, queue, members):
        members({"A": {"uz": None, "size": 1}})
        run(capsys, "cat-list", "Hadith scholars", "--source", "Some Article")
        rec = store.load()["categories"]["Category:Hadith scholars"]
        assert rec["status"] == "in_progress"
        assert rec["source"] == "Some Article"
        assert rec["members"] == 1 and rec["missing"] == 1

    def test_limit_reports_the_remainder(self, capsys, queue, members):
        members({f"A{i}": {"uz": None, "size": i + 1} for i in range(5)})
        _, out = run(capsys, "cat-list", "X", "--limit", "2")
        assert out[-2] == "MORE 3"
        assert out[-1] == "END"


class TestArtCats:
    def test_labels_reflect_stored_state(self, capsys, queue, monkeypatch):
        data = store.load()
        store.upsert_category(data, "Category:Done", status="exhausted")
        store.upsert_category(data, "Category:Open", status="in_progress")
        store.save(data)
        monkeypatch.setattr(wiki, "fetch_article_categories", lambda t: [
            "Category:726 births", "Category:Done", "Category:Open", "Category:Fresh",
        ])
        _, out = run(capsys, "art-cats", "Some Article")
        assert out[:4] == [
            "SKIP\tCategory:726 births",
            "DONE\tCategory:Done",
            "OPEN\tCategory:Open",
            "NEW\tCategory:Fresh",
        ]

    def test_new_categories_recorded_as_pending_with_source(self, capsys, queue, monkeypatch):
        monkeypatch.setattr(wiki, "fetch_article_categories",
                            lambda t: ["Category:Fresh", "Category:726 births"])
        run(capsys, "art-cats", "Some Article")
        cats = store.load()["categories"]
        assert cats["Category:Fresh"]["status"] == "pending"
        assert cats["Category:Fresh"]["source"] == "Some Article"
        # Maintenance categories are never added to the worklist.
        assert "Category:726 births" not in cats

    def test_missing_article(self, capsys, queue, monkeypatch):
        monkeypatch.setattr(wiki, "fetch_article_categories", lambda t: [])
        _, out = run(capsys, "art-cats", "Nope")
        assert out == ["MISSING Nope", "END"]


class TestCatTree:
    def test_parents_and_subs_labelled(self, capsys, queue, monkeypatch):
        monkeypatch.setattr(wiki, "fetch_category_parents", lambda c: ["Category:Up"])
        monkeypatch.setattr(wiki, "fetch_subcategories", lambda c: ["Category:Down"])
        _, out = run(capsys, "cat-tree", "X")
        assert out == ["PARENT\tNEW\tCategory:Up", "SUB\tNEW\tCategory:Down", "END"]


class TestQueueAdd:
    def test_added_dup_hasuz_missing(self, capsys, queue, titles):
        titles({
            "Good": {"uz": None, "size": 5000, "missing": False},
            "Exists": {"uz": "Bor", "size": 1000, "missing": False},
            "Nope": {"uz": None, "size": 0, "missing": True},
        })
        _, out = run(capsys, "queue-add", "Good", "Exists", "Nope", "--category", "X")
        assert out == [
            "ADDED\tGood\tmode=full\tsize=5000",
            "HASUZ\tExists\tuz=Bor",
            "MISSING\tNope",
            "END",
        ]

    def test_second_add_is_a_dup(self, capsys, queue, titles):
        titles({"Good": {"uz": None, "size": 5000, "missing": False}})
        run(capsys, "queue-add", "Good")
        _, out = run(capsys, "queue-add", "Good")
        assert out == ["DUP\tGood\tstatus=queued", "END"]

    def test_explicit_mode_overrides_size(self, capsys, queue, titles):
        titles({"Good": {"uz": None, "size": 500, "missing": False}})
        _, out = run(capsys, "queue-add", "Good", "--mode", "trim")
        assert out[0] == "ADDED\tGood\tmode=trim\tsize=500"

    def test_record_carries_category_and_url(self, capsys, queue, titles):
        titles({"Good": {"uz": None, "size": 5000, "missing": False}})
        run(capsys, "queue-add", "Good", "--category", "Hadith scholars")
        rec = store.load()["articles"]["Good"]
        assert rec["category"] == "Category:Hadith scholars"
        assert rec["url"] == "https://en.wikipedia.org/wiki/Good"
        assert rec["status"] == "queued"


class TestReject:
    def test_reason_is_recorded(self, capsys, queue):
        _, out = run(capsys, "reject", "Bad One", "--reason", "modern militant")
        assert out == ["REJECTED\tBad One", "END"]
        rec = store.load()["articles"]["Bad One"]
        assert rec["status"] == "rejected"
        assert rec["reject_reason"] == "modern militant"

    def test_rejecting_a_known_title_reports_dup(self, capsys, queue):
        run(capsys, "reject", "X", "--reason", "a")
        _, out = run(capsys, "reject", "X", "--reason", "b")
        assert out == ["DUP\tX\tstatus=rejected", "END"]

    def test_reason_is_required(self, capsys, queue):
        with pytest.raises(SystemExit):
            cli.main(["reject", "X"])


class TestCatDoneStatusNext:
    def test_cat_done_marks_exhausted(self, capsys, queue):
        _, out = run(capsys, "cat-done", "Hadith scholars", "--note", "tugadi")
        assert out == ["DONE\tCategory:Hadith scholars", "END"]
        rec = store.load()["categories"]["Category:Hadith scholars"]
        assert rec["status"] == "exhausted" and rec["note"] == "tugadi"

    def test_status_on_empty_queue(self, capsys, queue):
        _, out = run(capsys, "status")
        assert out[0] == "QUEUED 0 TRANSLATED 0 PUBLISHED 0 REJECTED 0 FAILED 0"
        assert out[1] == "CATS pending=0 in_progress=0 exhausted=0 skipped=0"
        assert out[2] == "CURRENT\tnone"

    def test_status_shows_current_and_pending(self, capsys, queue):
        data = store.load()
        store.upsert_article(data, "A")
        store.upsert_category(data, "Category:Now", status="in_progress")
        store.upsert_category(data, "Category:Later", status="pending")
        store.save(data)
        _, out = run(capsys, "status")
        assert out[0].startswith("QUEUED 1")
        assert "CURRENT\tCategory:Now" in out
        assert "PENDING\tCategory:Later" in out

    def test_next_lists_smallest_first(self, capsys, queue):
        data = store.load()
        store.upsert_article(data, "Big", size=20000, mode="trim")
        store.upsert_article(data, "Small", size=100, mode="full")
        store.save(data)
        _, out = run(capsys, "next", "-n", "2")
        assert out == ["100\tfull\tSmall", "20000\ttrim\tBig", "END"]

    def test_next_json_is_machine_readable(self, capsys, queue):
        data = store.load()
        store.upsert_article(data, "A", size=100, mode="full")
        store.save(data)
        code = cli.main(["next", "--json"])
        rows = json.loads(capsys.readouterr().out)
        assert code == 0
        assert rows[0]["title"] == "A" and rows[0]["mode"] == "full"


class TestErrorHandling:
    def test_api_failure_reports_on_stderr_and_exits_nonzero(self, capsys, queue, monkeypatch):
        def boom(category):
            raise RuntimeError("API yiqildi")
        monkeypatch.setattr(wiki, "fetch_category_members", boom)
        code = cli.main(["cat-list", "X"])
        captured = capsys.readouterr()
        assert code == cli.EXIT_ERROR
        assert captured.err.strip() == "ERROR API yiqildi"
        assert captured.out == ""

    def test_unknown_command_exits(self):
        with pytest.raises(SystemExit):
            cli.main(["no-such-command"])


class TestRejectOverridesQueued:
    def test_queued_article_can_be_pulled_back_out(self, capsys, queue):
        data = store.load()
        store.upsert_article(data, "Risky", status="queued")
        store.save(data)
        _, out = run(capsys, "reject", "Risky", "--reason", "Salafi movement figure")
        assert out == ["REJECTED\tRisky\twas=queued", "END"]
        rec = store.load()["articles"]["Risky"]
        assert rec["status"] == "rejected"
        assert rec["reject_reason"] == "Salafi movement figure"

    def test_published_article_is_not_pulled_back(self, capsys, queue):
        data = store.load()
        store.upsert_article(data, "Done")
        store.mark(data, "Done", "published")
        store.save(data)
        _, out = run(capsys, "reject", "Done", "--reason", "second thoughts")
        assert out == ["DUP\tDone\tstatus=published", "END"]
        assert store.load()["articles"]["Done"]["status"] == "published"


class TestScreen:
    def test_risk_and_clear_lines(self, capsys, queue, monkeypatch):
        monkeypatch.setattr(wiki, "fetch_titles_categories", lambda t: {
            "Risky": ["Category:Hadith scholars", "Category:Wahhabis"],
            "Fine": ["Category:Hadith scholars"],
        })
        _, out = run(capsys, "screen", "Risky", "Fine")
        assert out == ["RISK\tRisky\tCategory:Wahhabis", "CLEAR\tFine", "END"]

    def test_several_risky_categories_are_joined(self, capsys, queue, monkeypatch):
        monkeypatch.setattr(wiki, "fetch_titles_categories", lambda t: {
            "X": ["Category:Wahhabis", "Category:Moroccan Salafis"],
        })
        _, out = run(capsys, "screen", "X")
        assert out[0] == "RISK\tX\tCategory:Wahhabis|Category:Moroccan Salafis"

    def test_unknown_title_counts_as_clear(self, capsys, queue, monkeypatch):
        monkeypatch.setattr(wiki, "fetch_titles_categories", lambda t: {})
        _, out = run(capsys, "screen", "Nope")
        assert out == ["CLEAR\tNope", "END"]


class TestRequeue:
    """The mirror of reject: a judgment can be revised."""

    def test_rejected_article_comes_back(self, capsys, queue, titles):
        titles({"X": {"uz": None, "size": 5000, "missing": False}})
        run(capsys, "reject", "X", "--reason", "screen: living-figure category")
        _, out = run(capsys, "requeue", "X")
        assert out == ["REQUEUED\tX\tmode=full\tsize=5000", "END"]
        rec = store.load()["articles"]["X"]
        assert rec["status"] == "queued"
        assert rec["reject_reason"] is None

    def test_mode_is_recomputed_from_the_current_size(self, capsys, queue, titles):
        titles({"X": {"uz": None, "size": 20000, "missing": False}})
        run(capsys, "reject", "X", "--reason", "a")
        _, out = run(capsys, "requeue", "X")
        assert out[0] == "REQUEUED\tX\tmode=trim\tsize=20000"

    def test_published_article_is_not_touched(self, capsys, queue, titles):
        titles({"X": {"uz": None, "size": 100, "missing": False}})
        run(capsys, "queue-add", "X")
        data = store.load()
        store.mark(data, "X", "published")
        store.save(data)
        _, out = run(capsys, "requeue", "X")
        assert out == ["SKIP\tX\tstatus=published", "END"]
        assert store.load()["articles"]["X"]["status"] == "published"

    def test_unknown_title(self, capsys, queue, titles):
        titles({})
        _, out = run(capsys, "requeue", "Nope")
        assert out == ["UNKNOWN\tNope", "END"]
