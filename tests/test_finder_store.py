"""Tests for finder/store.py — the queue file that survives the agent losing context."""

import json
import pytest

from finder import store


@pytest.fixture
def queue(tmp_path):
    """Point the store at a throwaway queue file."""
    original = store.get_path()
    store.set_path(tmp_path / "data" / "queue.json")
    yield store.get_path()
    store.set_path(original)


class TestLoadSave:
    def test_load_without_file_returns_skeleton(self, queue):
        data = store.load()
        assert data["categories"] == {}
        assert data["articles"] == {}
        assert data["stats"] == {s: 0 for s in store.ARTICLE_STATUSES}

    def test_save_creates_parent_directory(self, queue):
        store.save(store.load())
        assert queue.exists()

    def test_round_trip(self, queue):
        data = store.load()
        store.upsert_article(data, "A", size=100)
        store.save(data)
        assert store.load()["articles"]["A"]["size"] == 100

    def test_corrupt_file_raises_rather_than_resetting(self, queue):
        queue.parent.mkdir(parents=True)
        queue.write_text("{not json", encoding="utf-8")
        with pytest.raises(RuntimeError):
            store.load()

    def test_save_is_atomic_no_tmp_left_behind(self, queue):
        store.save(store.load())
        assert list(queue.parent.glob("*.tmp")) == []

    def test_updated_at_refreshed_on_save(self, queue):
        data = store.load()
        data["updated_at"] = "old"
        store.save(data)
        assert data["updated_at"] != "old"


class TestArticles:
    def test_upsert_returns_added_then_dup(self, queue):
        data = store.load()
        assert store.upsert_article(data, "A")[0] == "added"
        assert store.upsert_article(data, "A") == ("dup", "queued")

    def test_upsert_never_downgrades_status(self, queue):
        data = store.load()
        store.upsert_article(data, "A")
        store.mark(data, "A", "published")
        outcome, status = store.upsert_article(data, "A", status="queued")
        assert (outcome, status) == ("dup", "published")
        assert data["articles"]["A"]["status"] == "published"

    def test_rejected_article_is_never_offered_again(self, queue):
        data = store.load()
        store.upsert_article(data, "A", status="rejected", reject_reason="radical")
        assert store.upsert_article(data, "A")[1] == "rejected"
        assert store.next_queued(data, 10) == []

    def test_mark_unknown_title_returns_false(self, queue):
        assert store.mark(store.load(), "Nope", "translated") is False

    def test_mark_translated_sets_timestamp(self, queue):
        data = store.load()
        store.upsert_article(data, "A")
        store.mark(data, "A", "translated", run_id="2026-09-11")
        rec = data["articles"]["A"]
        assert rec["translated_at"] is not None
        assert rec["published_at"] is None
        assert rec["run_id"] == "2026-09-11"

    def test_mark_published_sets_timestamp(self, queue):
        data = store.load()
        store.upsert_article(data, "A")
        store.mark(data, "A", "published")
        assert data["articles"]["A"]["published_at"] is not None

    def test_known_titles(self, queue):
        data = store.load()
        store.upsert_article(data, "A")
        store.upsert_article(data, "B", status="rejected")
        assert store.known_titles(data) == {"A", "B"}


class TestNextQueued:
    def test_smallest_first(self, queue):
        data = store.load()
        for title, size in [("Big", 30000), ("Small", 1000), ("Mid", 9000)]:
            store.upsert_article(data, title, size=size)
        assert [r["title"] for r in store.next_queued(data, 3)] == ["Small", "Mid", "Big"]

    def test_only_queued_are_returned(self, queue):
        data = store.load()
        store.upsert_article(data, "A", size=1)
        store.upsert_article(data, "B", size=2)
        store.mark(data, "B", "translated")
        assert [r["title"] for r in store.next_queued(data, 10)] == ["A"]

    def test_limit_respected(self, queue):
        data = store.load()
        for i in range(5):
            store.upsert_article(data, f"A{i}", size=i)
        assert len(store.next_queued(data, 2)) == 2

    def test_rows_carry_the_title(self, queue):
        data = store.load()
        store.upsert_article(data, "A", size=1, mode="trim")
        row = store.next_queued(data, 1)[0]
        assert row["title"] == "A" and row["mode"] == "trim"


class TestCategories:
    def test_upsert_creates_then_updates(self, queue):
        data = store.load()
        store.upsert_category(data, "Category:X", source="seed")
        store.upsert_category(data, "Category:X", status="exhausted")
        rec = data["categories"]["Category:X"]
        assert rec["status"] == "exhausted"
        assert rec["source"] == "seed"

    def test_current_category_is_the_in_progress_one(self, queue):
        data = store.load()
        store.upsert_category(data, "Category:A", status="exhausted")
        store.upsert_category(data, "Category:B", status="in_progress")
        assert store.current_category(data) == "Category:B"

    def test_current_is_none_when_nothing_open(self, queue):
        data = store.load()
        store.upsert_category(data, "Category:A", status="exhausted")
        assert store.current_category(data) is None

    def test_pending_categories_listed(self, queue):
        data = store.load()
        store.upsert_category(data, "Category:A", status="pending")
        store.upsert_category(data, "Category:B", status="exhausted")
        assert store.pending_categories(data) == ["Category:A"]

    def test_source_records_navigation_trail(self, queue):
        data = store.load()
        store.upsert_category(data, "Category:B", source="Some Article")
        assert data["categories"]["Category:B"]["source"] == "Some Article"


class TestRecount:
    def test_stats_rebuilt_on_save(self, queue):
        data = store.load()
        store.upsert_article(data, "A")
        store.upsert_article(data, "B", status="rejected")
        store.upsert_article(data, "C")
        store.mark(data, "C", "published")
        store.save(data)
        stats = json.loads(queue.read_text(encoding="utf-8"))["stats"]
        assert stats == {"queued": 1, "translated": 0, "published": 1,
                         "rejected": 1, "failed": 0}
