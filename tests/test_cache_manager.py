"""Tests for core/cache_manager.py — WikiCache in-memory memoization."""

import pytest
from core.cache_manager import WikiCache


@pytest.fixture
def cache():
    return WikiCache()


# ── QID cache ─────────────────────────────────────────────────────────────────

class TestQIDCache:
    def test_miss_returns_none(self, cache):
        assert cache.get_qid("en", "Albert Einstein") is None

    def test_miss_increments_stat(self, cache):
        cache.get_qid("en", "Albert Einstein")
        assert cache.stats["qid_misses"] == 1

    def test_set_get_roundtrip(self, cache):
        cache.set_qid("en", "Albert Einstein", "Q937")
        assert cache.get_qid("en", "Albert Einstein") == "Q937"

    def test_hit_increments_stat(self, cache):
        cache.set_qid("en", "Albert Einstein", "Q937")
        cache.get_qid("en", "Albert Einstein")
        assert cache.stats["qid_hits"] == 1

    def test_none_stored_as_sentinel(self, cache):
        cache.set_qid("en", "NoSuchPage", None)
        assert cache.qid_cache["en:NoSuchPage"] == "NONE"

    def test_sentinel_returns_none_not_string(self, cache):
        cache.set_qid("en", "NoSuchPage", None)
        result = cache.get_qid("en", "NoSuchPage")
        assert result is None
        assert result != "NONE"

    def test_sentinel_counts_as_hit(self, cache):
        cache.set_qid("en", "NoSuchPage", None)
        cache.get_qid("en", "NoSuchPage")
        assert cache.stats["qid_hits"] == 1
        assert cache.stats["qid_misses"] == 0

    def test_key_format(self, cache):
        cache.set_qid("en", "Albert Einstein", "Q937")
        assert "en:Albert Einstein" in cache.qid_cache

    def test_different_site_codes_are_independent(self, cache):
        cache.set_qid("en", "Python", "Q28865")
        cache.set_qid("uz", "Python", "Q99999")
        assert cache.get_qid("en", "Python") == "Q28865"
        assert cache.get_qid("uz", "Python") == "Q99999"


# ── Sitelink cache ────────────────────────────────────────────────────────────

class TestSitelinkCache:
    def test_miss_returns_none(self, cache):
        assert cache.get_sitelink("Q937", "uzwiki") is None

    def test_miss_increments_stat(self, cache):
        cache.get_sitelink("Q937", "uzwiki")
        assert cache.stats["sitelink_misses"] == 1

    def test_set_get_roundtrip(self, cache):
        cache.set_sitelink("Q937", "uzwiki", "Albert Eynshteyn")
        assert cache.get_sitelink("Q937", "uzwiki") == "Albert Eynshteyn"

    def test_hit_increments_stat(self, cache):
        cache.set_sitelink("Q937", "uzwiki", "Albert Eynshteyn")
        cache.get_sitelink("Q937", "uzwiki")
        assert cache.stats["sitelink_hits"] == 1

    def test_default_target_site_is_uzwiki(self, cache):
        cache.set_sitelink("Q937", "uzwiki", "Albert Eynshteyn")
        assert cache.get_sitelink("Q937") == "Albert Eynshteyn"

    def test_none_stored_as_sentinel(self, cache):
        cache.set_sitelink("Q937", "uzwiki", None)
        assert cache.sitelink_cache["Q937:uzwiki"] == "NONE"

    def test_sentinel_returns_none(self, cache):
        cache.set_sitelink("Q937", "uzwiki", None)
        assert cache.get_sitelink("Q937", "uzwiki") is None

    def test_different_target_sites_are_independent(self, cache):
        cache.set_sitelink("Q937", "uzwiki", "Albert Eynshteyn")
        cache.set_sitelink("Q937", "enwiki", "Albert Einstein")
        assert cache.get_sitelink("Q937", "uzwiki") == "Albert Eynshteyn"
        assert cache.get_sitelink("Q937", "enwiki") == "Albert Einstein"


# ── Redirect cache ────────────────────────────────────────────────────────────

class TestRedirectCache:
    def test_miss_returns_none(self, cache):
        assert cache.get_redirect("en", "CR7") is None

    def test_miss_increments_stat(self, cache):
        cache.get_redirect("en", "CR7")
        assert cache.stats["redirect_misses"] == 1

    def test_set_get_roundtrip(self, cache):
        cache.set_redirect("en", "CR7", "Cristiano Ronaldo")
        assert cache.get_redirect("en", "CR7") == "Cristiano Ronaldo"

    def test_hit_increments_stat(self, cache):
        cache.set_redirect("en", "CR7", "Cristiano Ronaldo")
        cache.get_redirect("en", "CR7")
        assert cache.stats["redirect_hits"] == 1

    def test_empty_string_stored_as_sentinel(self, cache):
        cache.set_redirect("en", "Ghost", "")
        assert cache.redirect_cache["en:Ghost"] == "NONE"

    def test_sentinel_returns_none(self, cache):
        cache.set_redirect("en", "Ghost", "")
        assert cache.get_redirect("en", "Ghost") is None


# ── Cache size & independence ─────────────────────────────────────────────────

class TestCacheSizeAndIndependence:
    def test_cache_size_empty(self, cache):
        assert cache.get_cache_size() == {"qid": 0, "sitelink": 0, "redirect": 0, "total": 0}

    def test_cache_size_after_sets(self, cache):
        cache.set_qid("en", "A", "Q1")
        cache.set_qid("en", "B", "Q2")
        cache.set_sitelink("Q1", "uzwiki", "Title")
        sizes = cache.get_cache_size()
        assert sizes["qid"] == 2
        assert sizes["sitelink"] == 1
        assert sizes["redirect"] == 0
        assert sizes["total"] == 3

    def test_qid_set_does_not_affect_sitelink_or_redirect(self, cache):
        cache.set_qid("en", "Test", "Q999")
        assert len(cache.sitelink_cache) == 0
        assert len(cache.redirect_cache) == 0

    def test_all_caches_independent(self, cache):
        cache.set_qid("en", "X", "Q1")
        cache.set_sitelink("Q1", "uzwiki", "Y")
        cache.set_redirect("en", "Z", "W")
        assert cache.get_cache_size()["total"] == 3
