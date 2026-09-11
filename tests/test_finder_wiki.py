"""Tests for finder/wiki.py — the Wikipedia reads behind article discovery."""

import pytest

from finder import wiki


@pytest.fixture
def api(monkeypatch):
    """Replace wiki_api with a queue of canned responses; record the params sent."""
    calls = []
    responses = []

    def fake(params, lang="en", domain="wikipedia", timeout=30):
        calls.append(params)
        return responses.pop(0)

    monkeypatch.setattr(wiki, "wiki_api", fake)
    return type("Api", (), {"calls": calls, "responses": responses})


class TestNameHelpers:
    def test_prefix_added(self):
        assert wiki.normalize_category_name("Hadith scholars") == "Category:Hadith scholars"

    def test_prefix_not_doubled(self):
        assert wiki.normalize_category_name("Category:X") == "Category:X"

    def test_lowercase_prefix_normalised(self):
        assert wiki.normalize_category_name("category:X") == "Category:X"

    def test_strip_prefix(self):
        assert wiki.strip_category_prefix("Category:X") == "X"
        assert wiki.strip_category_prefix("X") == "X"

    def test_make_url_encodes(self):
        assert wiki.make_url("Abu Thawr") == "https://en.wikipedia.org/wiki/Abu_Thawr"
        assert "%27" in wiki.make_url("Abu'l Abbas")


class TestMaintenanceCategories:
    @pytest.mark.parametrize("name", [
        "Category:726 births",
        "Category:1040s births",
        "Category:900 deaths",
        "Category:Islamic scholar stubs",
        "Category:All articles with dead links",
        "Category:Articles containing Arabic-language text",
        "Category:Use dmy dates from March 2024",
        "Category:CS1 Arabic-language sources (ar)",
        "Category:Year of birth unknown",
        "Category:Short description matches Wikidata",
    ])
    def test_noise_is_skipped(self, name):
        assert wiki.is_maintenance_category(name) is True

    @pytest.mark.parametrize("name", [
        "Category:Hadith scholars",
        "Category:Hanafi fiqh scholars",
        "Category:8th-century jurists",
        "Category:Sufi mystics",
        "Category:Muslim ascetics",
    ])
    def test_topical_categories_are_kept(self, name):
        assert wiki.is_maintenance_category(name) is False


class TestFetchCategoryMembers:
    def test_size_and_uz_read_from_one_response(self, api):
        api.responses.append({"query": {"pages": [
            {"title": "A", "length": 5296, "langlinks": []},
            {"title": "B", "length": 24486, "langlinks": [{"lang": "uz", "title": "B-uz"}]},
        ]}})
        result = wiki.fetch_category_members("Hadith scholars")
        assert result == {
            "A": {"uz": None, "size": 5296},
            "B": {"uz": "B-uz", "size": 24486},
        }

    def test_single_request_asks_for_langlinks_and_info(self, api):
        api.responses.append({"query": {"pages": []}})
        wiki.fetch_category_members("Hadith scholars")
        params = api.calls[0]
        assert params["prop"] == "langlinks|info"
        assert params["gcmtitle"] == "Category:Hadith scholars"
        assert params["redirects"] == "1"

    def test_continuation_merges_without_losing_values(self, api):
        # The API can split a page's props across responses: the second
        # response must not blank out a title already known.
        api.responses.append({
            "query": {"pages": [{"title": "A", "length": 100,
                                 "langlinks": [{"lang": "uz", "title": "A-uz"}]}]},
            "continue": {"gcmcontinue": "x"},
        })
        api.responses.append({"query": {"pages": [{"title": "A"}]}})
        result = wiki.fetch_category_members("X")
        assert result["A"] == {"uz": "A-uz", "size": 100}
        assert len(api.calls) == 2

    def test_uz_status_view_drops_sizes(self, api):
        api.responses.append({"query": {"pages": [
            {"title": "A", "length": 1, "langlinks": []},
            {"title": "B", "length": 2, "langlinks": [{"lang": "uz", "title": "B-uz"}]},
        ]}})
        assert wiki.fetch_category_uz_status("X") == {"A": None, "B": "B-uz"}


class TestFetchTitlesInfo:
    def test_missing_article_flagged(self, api):
        api.responses.append({"query": {"pages": [{"title": "Nope", "missing": True}]}})
        assert wiki.fetch_titles_info(["Nope"])["Nope"]["missing"] is True

    def test_redirect_source_resolves_to_target(self, api):
        api.responses.append({"query": {
            "redirects": [{"from": "Al-Bukhari", "to": "Muhammad al-Bukhari"}],
            "pages": [{"title": "Muhammad al-Bukhari", "length": 42059,
                       "langlinks": [{"lang": "uz", "title": "Imom al-Buxoriy"}]}],
        }})
        result = wiki.fetch_titles_info(["Al-Bukhari"])
        assert result["Al-Bukhari"]["uz"] == "Imom al-Buxoriy"
        assert result["Al-Bukhari"]["size"] == 42059

    def test_batched_by_api_batch_size(self, api, monkeypatch):
        monkeypatch.setattr(wiki.config, "API_BATCH_SIZE", 2)
        for _ in range(2):
            api.responses.append({"query": {"pages": []}})
        wiki.fetch_titles_info(["A", "B", "C"])
        assert len(api.calls) == 2
        assert api.calls[0]["titles"] == "A|B"


class TestCategoryNavigation:
    def test_article_categories(self, api):
        api.responses.append({"query": {"pages": [
            {"title": "A", "categories": [{"title": "Category:X"}, {"title": "Category:Y"}]}
        ]}})
        assert wiki.fetch_article_categories("A") == ["Category:X", "Category:Y"]

    def test_missing_article_has_no_categories(self, api):
        api.responses.append({"query": {"pages": [{"title": "A", "missing": True}]}})
        assert wiki.fetch_article_categories("A") == []

    def test_article_without_categories(self, api):
        api.responses.append({"query": {"pages": [{"title": "A"}]}})
        assert wiki.fetch_article_categories("A") == []

    def test_category_parents(self, api):
        api.responses.append({"query": {"pages": [
            {"title": "Category:X", "categories": [{"title": "Category:Parent"}]}
        ]}})
        assert wiki.fetch_category_parents("X") == ["Category:Parent"]

    def test_subcategories(self, api):
        api.responses.append({"query": {"categorymembers": [
            {"title": "Category:Sub1"}, {"title": "Category:Sub2"},
        ]}})
        assert wiki.fetch_subcategories("X") == ["Category:Sub1", "Category:Sub2"]
        assert api.calls[0]["cmtype"] == "subcat"


class TestRiskScreening:
    @pytest.mark.parametrize("category", [
        "Category:Moroccan Salafis",
        "Category:Albanian Salafis",
        "Category:Wahhabis",
        "Category:Proto-Salafists",
        "Category:Ahl-i Hadith people",
        "Category:Indian Islamists",
        "Category:Al-Qaeda members",
        "Category:Islamic terrorism",
        "Category:People imprisoned on terrorism charges",
        "Category:Living people",
    ])
    def test_decisive_categories_are_flagged(self, category):
        assert wiki.risky_categories([category]) == [category]

    @pytest.mark.parametrize("category", [
        "Category:Hadith scholars",
        "Category:Shafi'is",
        "Category:Quranic exegesis scholars",
        "Category:Sufi mystics",
        "Category:12th-century Arabic writers",
    ])
    def test_classical_categories_are_clear(self, category):
        assert wiki.risky_categories([category]) == []

    def test_only_the_risky_subset_is_returned(self):
        cats = ["Category:Hadith scholars", "Category:Wahhabis", "Category:Shafi'is"]
        assert wiki.risky_categories(cats) == ["Category:Wahhabis"]

    def test_categories_batched_and_continued(self, api, monkeypatch):
        monkeypatch.setattr(wiki.config, "API_BATCH_SIZE", 50)
        api.responses.append({
            "query": {"pages": [{"title": "A", "categories": [{"title": "Category:X"}]}]},
            "continue": {"clcontinue": "1|Y"},
        })
        api.responses.append({
            "query": {"pages": [{"title": "A", "categories": [{"title": "Category:Y"}]}]},
        })
        assert wiki.fetch_titles_categories(["A"]) == {"A": ["Category:X", "Category:Y"]}

    def test_redirect_source_carries_the_categories(self, api):
        api.responses.append({"query": {
            "redirects": [{"from": "Short", "to": "Full Title"}],
            "pages": [{"title": "Full Title", "categories": [{"title": "Category:X"}]}],
        }})
        assert wiki.fetch_titles_categories(["Short"])["Short"] == ["Category:X"]

    @pytest.mark.parametrize("category", [
        "Category:Moro Islamic Liberation Front members",
        "Category:Palestine Liberation Organisation members",
        "Category:Afghan mujahideen",
        "Category:Hamas members",
        "Category:Hezbollah members",
        "Category:Chechen separatists",
        "Category:Warlords",
    ])
    def test_armed_movements_without_a_creed_word_are_flagged(self, category):
        # These name a cause, not a doctrine: "Salafi", "jihad" and "militant"
        # never appear in them, so they slipped through the first version.
        assert wiki.risky_categories([category]) == [category]

    @pytest.mark.parametrize("category", [
        "Category:Mujahid ibn Jabr",          # classical mufassir, not a movement
        "Category:People from the Bahamas",   # not Hamas
        "Category:Rebellions in the Ottoman Empire",  # medieval history is fine
        "Category:Basil of Caesarea",         # not ISIL
    ])
    def test_substring_lookalikes_are_not_flagged(self, category):
        assert wiki.risky_categories([category]) == []

    @pytest.mark.parametrize("category", [
        "Category:Afghan mujahideen",
        "Category:Hamas members",
        "Category:Syrian rebels",
    ])
    def test_the_movement_spellings_still_flag(self, category):
        assert wiki.risky_categories([category]) == [category]
