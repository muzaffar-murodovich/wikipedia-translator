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


# ── append_file ───────────────────────────────────────────────────────────────

class TestAppendFile:
    def test_appends_content_to_existing(self, tmp_path):
        f = tmp_path / "log.txt"
        f.write_text("line1", encoding="utf-8")
        FileHandler.append_file(str(f), "line2")
        assert f.read_text(encoding="utf-8") == "line1line2"

    def test_creates_new_file_when_absent(self, tmp_path):
        path = str(tmp_path / "new.txt")
        result = FileHandler.append_file(path, "content")
        assert result is True
        assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "content"


# ── file_exists ───────────────────────────────────────────────────────────────

class TestFileExists:
    def test_returns_true_for_existing_file(self, tmp_path):
        f = tmp_path / "exists.txt"
        f.write_text("x", encoding="utf-8")
        assert FileHandler.file_exists(str(f)) is True

    def test_returns_false_for_missing_file(self, tmp_path):
        assert FileHandler.file_exists(str(tmp_path / "no.txt")) is False


# ── get_file_size ─────────────────────────────────────────────────────────────

class TestGetFileSize:
    def test_returns_correct_byte_count(self, tmp_path):
        f = tmp_path / "sized.txt"
        f.write_bytes(b"abc")
        assert FileHandler.get_file_size(str(f)) == 3

    def test_returns_zero_for_missing_file(self, tmp_path):
        assert FileHandler.get_file_size(str(tmp_path / "missing.txt")) == 0


# ── read_lines ────────────────────────────────────────────────────────────────

class TestReadLines:
    def test_returns_list_of_lines(self, tmp_path):
        f = tmp_path / "lines.txt"
        f.write_text("a\nb\nc", encoding="utf-8")
        lines = FileHandler.read_lines(str(f))
        assert isinstance(lines, list)
        assert len(lines) == 3

    def test_returns_empty_list_on_missing(self, tmp_path):
        result = FileHandler.read_lines(str(tmp_path / "nope.txt"))
        assert result == []


# ── create_backup ─────────────────────────────────────────────────────────────

class TestCreateBackup:
    def test_creates_dot_backup_file(self, tmp_path):
        f = tmp_path / "original.txt"
        f.write_text("data", encoding="utf-8")
        backup_path = FileHandler.create_backup(str(f))
        assert backup_path is not None
        assert (tmp_path / "original.txt.backup").exists()

    def test_backup_contains_original_content(self, tmp_path):
        f = tmp_path / "original.txt"
        f.write_text("original data", encoding="utf-8")
        FileHandler.create_backup(str(f))
        backup = (tmp_path / "original.txt.backup")
        assert backup.read_text(encoding="utf-8") == "original data"

    def test_returns_none_for_missing_source(self, tmp_path):
        result = FileHandler.create_backup(str(tmp_path / "nope.txt"))
        assert result is None


# ── delete_file ───────────────────────────────────────────────────────────────

class TestDeleteFile:
    def test_removes_existing_file(self, tmp_path):
        f = tmp_path / "del.txt"
        f.write_text("x", encoding="utf-8")
        assert FileHandler.delete_file(str(f)) is True
        assert not f.exists()

    def test_returns_false_for_missing_file(self, tmp_path):
        assert FileHandler.delete_file(str(tmp_path / "nope.txt")) is False


# ── ensure_dir_exists ─────────────────────────────────────────────────────────

class TestEnsureDirExists:
    def test_creates_nested_directory(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c"
        result = FileHandler.ensure_dir_exists(str(nested))
        assert result is True
        assert nested.exists()

    def test_ok_when_directory_already_exists(self, tmp_path):
        result = FileHandler.ensure_dir_exists(str(tmp_path))
        assert result is True
