"""Tests for the move-database / cleanup-legacy flow.

The whole flow uses ``data_dir()`` for the JSON pointer file, so we
override the ``LOCALAPPDATA`` env var (used by ``data_dir`` on Windows)
and the equivalent fallback to redirect everything into a tmp dir.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from budget_tracker import config


@pytest.fixture
def fake_data_dir(tmp_path, monkeypatch):
    """Redirect all per-user data writes (including config.json and the
    default DB path) to a per-test tmp directory."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    # POSIX fallback uses ~/.local/share — short-circuit just in case.
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    return config.data_dir()


def _seed_db(path: Path, payload: bytes = b"sqlite-stand-in") -> None:
    path.write_bytes(payload)


def test_db_path_falls_back_to_default(fake_data_dir):
    assert config.db_path() == config.default_db_path()
    assert config.load_app_config() == {}


def test_save_and_load_config_roundtrip(fake_data_dir):
    config.save_app_config({"foo": "bar", "n": 1})
    assert config.load_app_config() == {"foo": "bar", "n": 1}


def test_load_app_config_recovers_from_garbage(fake_data_dir):
    config.app_config_path().write_text("{ not json", encoding="utf-8")
    assert config.load_app_config() == {}


def test_db_path_honours_pointer_when_set(fake_data_dir, tmp_path):
    custom = tmp_path / "custom" / "budget.sqlite3"
    custom.parent.mkdir()
    config.save_app_config({config.KEY_DB_PATH: str(custom)})
    assert config.db_path() == custom


# move_database ------------------------------------------------------------

from budget_tracker.services.db_location_service import (
    cleanup_legacy_db_file,
    is_default_location,
    move_database,
    revert_to_default,
)


def test_move_database_copies_and_records_legacy(fake_data_dir, tmp_path):
    src = config.default_db_path()
    _seed_db(src, b"abc")

    dest_dir = tmp_path / "elsewhere"
    new_path = move_database(dest_dir)

    assert new_path == dest_dir / "budget.sqlite3"
    assert new_path.exists()
    assert new_path.read_bytes() == b"abc"

    cfg = config.load_app_config()
    assert cfg[config.KEY_DB_PATH] == str(new_path)
    assert cfg[config.KEY_LEGACY_DB_PATH] == str(src)
    assert config.db_path() == new_path
    assert is_default_location() is False


def test_move_refuses_when_target_exists(fake_data_dir, tmp_path):
    _seed_db(config.default_db_path())
    dest_dir = tmp_path / "elsewhere"
    dest_dir.mkdir()
    (dest_dir / "budget.sqlite3").write_bytes(b"existing")

    with pytest.raises(FileExistsError):
        move_database(dest_dir)


def test_move_refuses_when_source_missing(fake_data_dir, tmp_path):
    with pytest.raises(FileNotFoundError):
        move_database(tmp_path / "elsewhere")


def test_move_refuses_when_source_equals_destination(fake_data_dir):
    src = config.default_db_path()
    _seed_db(src)
    with pytest.raises(ValueError):
        move_database(src.parent)


# cleanup_legacy_db_file --------------------------------------------------

def test_cleanup_legacy_removes_old_file_and_clears_flag(fake_data_dir, tmp_path):
    legacy = tmp_path / "old.sqlite3"
    legacy.write_bytes(b"old")
    config.save_app_config({config.KEY_LEGACY_DB_PATH: str(legacy)})

    cleanup_legacy_db_file()

    assert not legacy.exists()
    assert config.KEY_LEGACY_DB_PATH not in config.load_app_config()


def test_cleanup_legacy_is_noop_without_flag(fake_data_dir):
    config.save_app_config({"unrelated": "value"})
    cleanup_legacy_db_file()
    # The unrelated key still survives.
    assert config.load_app_config() == {"unrelated": "value"}


def test_cleanup_legacy_clears_flag_when_file_already_gone(fake_data_dir, tmp_path):
    config.save_app_config({config.KEY_LEGACY_DB_PATH: str(tmp_path / "gone.sqlite3")})
    cleanup_legacy_db_file()
    assert config.KEY_LEGACY_DB_PATH not in config.load_app_config()


# revert_to_default -------------------------------------------------------

def test_revert_to_default_clears_pointer(fake_data_dir, tmp_path):
    config.save_app_config({config.KEY_DB_PATH: str(tmp_path / "x.sqlite3")})
    result = revert_to_default()
    assert result == config.default_db_path()
    assert config.db_path() == config.default_db_path()
    assert config.KEY_DB_PATH not in config.load_app_config()
