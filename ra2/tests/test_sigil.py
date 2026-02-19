"""Tests for ra2.sigil"""

import pytest
from ra2 import sigil


@pytest.fixture(autouse=True)
def tmp_sigil_dir(monkeypatch, tmp_path):
    """Redirect sigil storage to a temp directory for each test."""
    d = str(tmp_path / "sigils")
    monkeypatch.setattr(sigil, "SIGIL_DIR", d)
    return d


class TestLoadSave:
    def test_load_empty(self):
        entries = sigil.load("test-stream")
        assert entries == []

    def test_save_and_load(self):
        entries = [(1, "fork\u2192context_sov"), (2, "token_burn\u2192compress")]
        sigil.save("s1", entries)
        loaded = sigil.load("s1")
        assert loaded == entries

    def test_fifo_on_save(self):
        entries = [(i, f"entry-{i}") for i in range(1, 25)]
        sigil.save("s1", entries)
        loaded = sigil.load("s1")
        assert len(loaded) == sigil.MAX_ENTRIES
        # Should keep the last 15
        assert loaded[0][0] == 10
        assert loaded[-1][0] == 24


class TestAppend:
    def test_append_single(self):
        entries = sigil.append("s1", "fork\u2192ctx")
        assert len(entries) == 1
        assert entries[0] == (1, "fork\u2192ctx")

    def test_append_multiple(self):
        sigil.append("s1", "entry-a")
        entries = sigil.append("s1", "entry-b")
        assert len(entries) == 2
        assert entries[0][1] == "entry-a"
        assert entries[1][1] == "entry-b"

    def test_fifo_eviction(self):
        for i in range(20):
            entries = sigil.append("s1", f"e-{i}")
        assert len(entries) == sigil.MAX_ENTRIES
        # Oldest entries should be gone
        bodies = [e[1] for e in entries]
        assert "e-0" not in bodies
        assert "e-19" in bodies


class TestSnapshot:
    def test_snapshot_empty(self):
        snap = sigil.snapshot("empty")
        assert snap == "(no sigils)"

    def test_snapshot_with_entries(self):
        sigil.append("s1", "fork\u2192context_sov")
        sigil.append("s1", "token_burn\u2192compress")
        snap = sigil.snapshot("s1")
        assert "\u03c31:" in snap
        assert "fork\u2192context_sov" in snap
        assert "\u03c32:" in snap
        assert "token_burn\u2192compress" in snap


class TestGenerateFromMessage:
    def test_fork_detection(self):
        body = sigil.generate_from_message("We forked to context_sov branch")
        assert body is not None
        assert "fork" in body
        assert "context_sov" in body

    def test_token_burn_detection(self):
        body = sigil.generate_from_message("Seeing token burn on this stream")
        assert body == "token_burn\u2192compress"

    def test_rate_limit_detection(self):
        body = sigil.generate_from_message("Hit a rate limit again")
        assert body == "rate_limit\u2192detected"

    def test_no_match(self):
        body = sigil.generate_from_message("Hello, how are you?")
        assert body is None
