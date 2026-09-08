"""Tests for utils/file_handler.py — file I/O operations via tmp_path."""

import json
from utils.file_handler import FileHandler


# ── read_file ─────────────────────────────────────────────────────────────────

class TestReadFile:
    def test_reads_existing_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world", encoding="utf-8")
        assert FileHandler.read_file(str(f)) == "hello world"

    def test_returns_empty_string_on_missing_file(self, tmp_path):
        result = FileHandler.read_file(str(tmp_path / "nonexistent.txt"))
        assert result == ""

    def test_utf8_roundtrip(self, tmp_path):
        uzbek = "Ўзбекистон — markaziy Osiyo davlati"
        f = tmp_path / "uzbek.txt"
        f.write_text(uzbek, encoding="utf-8")
        assert FileHandler.read_file(str(f)) == uzbek


# ── write_file ────────────────────────────────────────────────────────────────

class TestWriteFile:
    def test_creates_file_with_content(self, tmp_path):
        path = str(tmp_path / "out.txt")
        FileHandler.write_file(path, "data")
        assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "data"

    def test_returns_true_on_success(self, tmp_path):
        path = str(tmp_path / "out.txt")
        assert FileHandler.write_file(path, "data") is True

    def test_overwrites_existing_file(self, tmp_path):
        path = str(tmp_path / "out.txt")
        FileHandler.write_file(path, "old")
        FileHandler.write_file(path, "new")
        assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "new"

    def test_utf8_roundtrip(self, tmp_path):
        path = str(tmp_path / "out.txt")
        text = "oʻzbek tili"
        FileHandler.write_file(path, text)
        assert FileHandler.read_file(path) == text


# ── read_json ─────────────────────────────────────────────────────────────────

class TestReadJson:
    def test_reads_valid_json(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text(json.dumps({"key": "value"}), encoding="utf-8")
        result = FileHandler.read_json(str(f))
        assert result == {"key": "value"}

    def test_returns_empty_dict_on_missing_file(self, tmp_path):
        result = FileHandler.read_json(str(tmp_path / "missing.json"))
        assert result == {}

    def test_returns_empty_dict_on_invalid_json(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("NOT VALID JSON {{{{", encoding="utf-8")
        result = FileHandler.read_json(str(f))
        assert result == {}

    def test_reads_nested_dict(self, tmp_path):
        data = {"a": {"b": [1, 2, 3]}}
        f = tmp_path / "nested.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        assert FileHandler.read_json(str(f)) == data


# ── write_json ────────────────────────────────────────────────────────────────

class TestWriteJson:
    def test_writes_valid_json(self, tmp_path):
        path = str(tmp_path / "out.json")
        FileHandler.write_json(path, {"x": 2})
        assert json.loads((tmp_path / "out.json").read_text(encoding="utf-8")) == {"x": 2}

    def test_returns_true_on_success(self, tmp_path):
        path = str(tmp_path / "out.json")
        assert FileHandler.write_json(path, {}) is True

    def test_preserves_non_ascii_chars(self, tmp_path):
        path = str(tmp_path / "out.json")
        FileHandler.write_json(path, {"key": "oʻzbek"})
        raw = (tmp_path / "out.json").read_text(encoding="utf-8")
        # ensure_ascii=False means Uzbek chars appear literally, not as \uXXXX
        assert "oʻzbek" in raw
        assert "\\u" not in raw


# ── file_exists ───────────────────────────────────────────────────────────────

class TestFileExists:
    def test_returns_true_for_existing_file(self, tmp_path):
        f = tmp_path / "exists.txt"
        f.write_text("x", encoding="utf-8")
        assert FileHandler.file_exists(str(f)) is True

    def test_returns_false_for_missing_file(self, tmp_path):
        assert FileHandler.file_exists(str(tmp_path / "no.txt")) is False
