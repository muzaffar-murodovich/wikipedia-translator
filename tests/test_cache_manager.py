import pytest
from core.cache_manager import WikiCache


class TestWikiCacheQID:
    def test_miss_returns_none(self):
        cache = WikiCache()
        assert cache.get_qid("en", "Albert Einstein") is None

    def test_hit_returns_qid(self):
        cache = WikiCache()
        cache.set_qid("en", "Albert Einstein", "Q937")
        assert cache.get_qid("en", "Albert Einstein") == "Q937"

    def test_none_stored_as_sentinel(self):
        cache = WikiCache()
        cache.set_qid("en", "Missing Article", None)
        assert cache.qid_cache["en:Missing Article"] == "NONE"
        assert cache.get_qid("en", "Missing Article") is None

    def test_different_site_codes_are_independent(self):
        cache = WikiCache()
        cache.set_qid("en", "Test", "Q1")
        assert cache.get_qid("uz", "Test") is None

    def test_miss_increments_miss_stat(self):
        cache = WikiCache()
        cache.get_qid("en", "Unknown")
        assert cache.stats["qid_misses"] == 1
        assert cache.stats["qid_hits"] == 0

    def test_hit_increments_hit_stat(self):
        cache = WikiCache()
        cache.set_qid("en", "Test", "Q1")
        cache.get_qid("en", "Test")
        assert cache.stats["qid_hits"] == 1
        assert cache.stats["qid_misses"] == 0

    def test_none_sentinel_counts_as_hit(self):
        cache = WikiCache()
        cache.set_qid("en", "Missing", None)
        cache.get_qid("en", "Missing")
        assert cache.stats["qid_hits"] == 1


class TestWikiCacheSitelink:
    def test_miss_returns_none(self):
        cache = WikiCache()
        assert cache.get_sitelink("Q937") is None

    def test_hit_returns_title(self):
        cache = WikiCache()
        cache.set_sitelink("Q937", "uzwiki", "Albert Eynshteyn")
        assert cache.get_sitelink("Q937", "uzwiki") == "Albert Eynshteyn"

    def test_none_stored_as_sentinel(self):
        cache = WikiCache()
        cache.set_sitelink("Q937", "uzwiki", None)
        assert cache.sitelink_cache["Q937:uzwiki"] == "NONE"
        assert cache.get_sitelink("Q937", "uzwiki") is None

    def test_default_target_is_uzwiki(self):
        cache = WikiCache()
        cache.set_sitelink("Q937", "uzwiki", "Some Title")
        assert cache.get_sitelink("Q937") == "Some Title"

    def test_different_target_sites_are_independent(self):
        cache = WikiCache()
        cache.set_sitelink("Q937", "uzwiki", "UZ Title")
        assert cache.get_sitelink("Q937", "enwiki") is None

    def test_miss_increments_miss_stat(self):
        cache = WikiCache()
        cache.get_sitelink("Q999")
        assert cache.stats["sitelink_misses"] == 1

    def test_hit_increments_hit_stat(self):
        cache = WikiCache()
        cache.set_sitelink("Q937", "uzwiki", "Title")
        cache.get_sitelink("Q937")
        assert cache.stats["sitelink_hits"] == 1


class TestWikiCacheRedirect:
    def test_miss_returns_none(self):
        cache = WikiCache()
        assert cache.get_redirect("en", "Einstein") is None

    def test_hit_returns_target(self):
        cache = WikiCache()
        cache.set_redirect("en", "Einstein", "Albert Einstein")
        assert cache.get_redirect("en", "Einstein") == "Albert Einstein"

    def test_empty_string_stored_as_sentinel(self):
        cache = WikiCache()
        cache.set_redirect("en", "Test", "")
        assert cache.redirect_cache["en:Test"] == "NONE"
        assert cache.get_redirect("en", "Test") is None

    def test_miss_increments_miss_stat(self):
        cache = WikiCache()
        cache.get_redirect("en", "Unknown")
        assert cache.stats["redirect_misses"] == 1

    def test_hit_increments_hit_stat(self):
        cache = WikiCache()
        cache.set_redirect("en", "Test", "Target")
        cache.get_redirect("en", "Test")
        assert cache.stats["redirect_hits"] == 1


class TestWikiCacheSize:
    def test_empty_cache(self):
        cache = WikiCache()
        assert cache.get_cache_size() == {"qid": 0, "sitelink": 0, "redirect": 0, "total": 0}

    def test_size_reflects_entries(self):
        cache = WikiCache()
        cache.set_qid("en", "A", "Q1")
        cache.set_qid("en", "B", "Q2")
        cache.set_sitelink("Q1", "uzwiki", "Title")
        cache.set_redirect("en", "X", "Y")
        sizes = cache.get_cache_size()
        assert sizes["qid"] == 2
        assert sizes["sitelink"] == 1
        assert sizes["redirect"] == 1
        assert sizes["total"] == 4

    def test_overwrite_does_not_grow_cache(self):
        cache = WikiCache()
        cache.set_qid("en", "Article", "Q1")
        cache.set_qid("en", "Article", "Q2")
        assert cache.get_cache_size()["qid"] == 1
