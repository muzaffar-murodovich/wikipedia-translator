import json
import pytest
from pathlib import Path
from utils.file_handler import FileHandler


class TestReadFile:
    def test_reads_content(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world", encoding="utf-8")
        assert FileHandler.read_file(str(f)) == "hello world"

    def test_missing_file_returns_empty_string(self, tmp_path):
        assert FileHandler.read_file(str(tmp_path / "missing.txt")) == ""

    def test_utf8_content(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("Oʻzbekiston", encoding="utf-8")
        assert FileHandler.read_file(str(f)) == "Oʻzbekiston"


class TestWriteFile:
    def test_creates_and_writes(self, tmp_path):
        f = tmp_path / "out.txt"
        assert FileHandler.write_file(str(f), "test content") is True
        assert f.read_text(encoding="utf-8") == "test content"

    def test_overwrites_existing(self, tmp_path):
        f = tmp_path / "out.txt"
        f.write_text("old", encoding="utf-8")
        FileHandler.write_file(str(f), "new")
        assert f.read_text(encoding="utf-8") == "new"

    def test_returns_true_on_success(self, tmp_path):
        f = tmp_path / "a.txt"
        assert FileHandler.write_file(str(f), "") is True


class TestReadJson:
    def test_reads_valid_json(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text('{"key": "value"}', encoding="utf-8")
        assert FileHandler.read_json(str(f)) == {"key": "value"}

    def test_missing_file_returns_empty_dict(self, tmp_path):
        assert FileHandler.read_json(str(tmp_path / "missing.json")) == {}

    def test_invalid_json_returns_empty_dict(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("not json {{", encoding="utf-8")
        assert FileHandler.read_json(str(f)) == {}


class TestWriteJson:
    def test_writes_valid_json(self, tmp_path):
        f = tmp_path / "out.json"
        data = {"a": 1, "b": [1, 2]}
        assert FileHandler.write_json(str(f), data) is True
        assert json.loads(f.read_text(encoding="utf-8")) == data

    def test_preserves_unicode(self, tmp_path):
        f = tmp_path / "out.json"
        data = {"name": "Oʻzbekiston"}
        FileHandler.write_json(str(f), data)
        assert json.loads(f.read_text(encoding="utf-8"))["name"] == "Oʻzbekiston"


class TestFileExists:
    def test_existing_file_returns_true(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("x", encoding="utf-8")
        assert FileHandler.file_exists(str(f)) is True

    def test_missing_file_returns_false(self, tmp_path):
        assert FileHandler.file_exists(str(tmp_path / "nope.txt")) is False


class TestGetFileSize:
    def test_correct_byte_size(self, tmp_path):
        f = tmp_path / "size.txt"
        content = "hello"
        f.write_text(content, encoding="utf-8")
        assert FileHandler.get_file_size(str(f)) == len(content.encode("utf-8"))

    def test_missing_file_returns_zero(self, tmp_path):
        assert FileHandler.get_file_size(str(tmp_path / "none.txt")) == 0


class TestReadLines:
    def test_returns_list_of_lines(self, tmp_path):
        f = tmp_path / "lines.txt"
        f.write_text("line1\nline2\nline3", encoding="utf-8")
        lines = FileHandler.read_lines(str(f))
        assert len(lines) == 3
        assert lines[0] == "line1\n"

    def test_missing_file_returns_empty_list(self, tmp_path):
        assert FileHandler.read_lines(str(tmp_path / "nope.txt")) == []


class TestAppendFile:
    def test_appends_to_existing(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("first", encoding="utf-8")
        FileHandler.append_file(str(f), " second")
        assert f.read_text(encoding="utf-8") == "first second"

    def test_creates_if_missing(self, tmp_path):
        f = tmp_path / "new.txt"
        assert FileHandler.append_file(str(f), "data") is True
        assert f.read_text(encoding="utf-8") == "data"


class TestCreateBackup:
    def test_creates_backup_file(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("original", encoding="utf-8")
        backup = FileHandler.create_backup(str(f))
        assert backup == str(f) + ".backup"
        assert Path(backup).read_text(encoding="utf-8") == "original"

    def test_missing_file_returns_none(self, tmp_path):
        assert FileHandler.create_backup(str(tmp_path / "nope.txt")) is None


class TestDeleteFile:
    def test_deletes_existing_file(self, tmp_path):
        f = tmp_path / "del.txt"
        f.write_text("x", encoding="utf-8")
        assert FileHandler.delete_file(str(f)) is True
        assert not f.exists()

    def test_missing_file_returns_false(self, tmp_path):
        assert FileHandler.delete_file(str(tmp_path / "nope.txt")) is False


class TestEnsureDirExists:
    def test_creates_new_directory(self, tmp_path):
        d = tmp_path / "new_dir"
        assert not d.exists()
        assert FileHandler.ensure_dir_exists(str(d)) is True
        assert d.is_dir()

    def test_creates_nested_directories(self, tmp_path):
        d = tmp_path / "a" / "b" / "c"
        FileHandler.ensure_dir_exists(str(d))
        assert d.is_dir()

    def test_existing_directory_is_ok(self, tmp_path):
        assert FileHandler.ensure_dir_exists(str(tmp_path)) is True
