"""Tests for ra2.context_engine"""

import pytest
from ra2 import ledger, sigil, token_gate
from ra2.context_engine import build_context


@pytest.fixture(autouse=True)
def tmp_storage(monkeypatch, tmp_path):
    """Redirect all storage to temp directories."""
    monkeypatch.setattr(ledger, "LEDGER_DIR", str(tmp_path / "ledgers"))
    monkeypatch.setattr(sigil, "SIGIL_DIR", str(tmp_path / "sigils"))


class TestBuildContext:
    def test_basic_output_shape(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        result = build_context("test-stream", messages)
        assert "prompt" in result
        assert "token_estimate" in result
        assert isinstance(result["prompt"], str)
        assert isinstance(result["token_estimate"], int)

    def test_prompt_structure(self):
        messages = [
            {"role": "user", "content": "Let's build a context engine"},
        ]
        result = build_context("s1", messages)
        prompt = result["prompt"]
        assert "=== LEDGER ===" in prompt
        assert "=== SIGIL ===" in prompt
        assert "=== LIVE WINDOW ===" in prompt
        assert "Respond concisely" in prompt

    def test_live_window_content(self):
        messages = [
            {"role": "user", "content": "message one"},
            {"role": "assistant", "content": "response one"},
        ]
        result = build_context("s1", messages)
        assert "[user] message one" in result["prompt"]
        assert "[assistant] response one" in result["prompt"]

    def test_redaction_applied(self):
        messages = [
            {"role": "user", "content": "my key is sk-abc123def456ghi789jklmnopqrs"},
        ]
        result = build_context("s1", messages)
        assert "sk-abc" not in result["prompt"]
        assert "[REDACTED_SECRET]" in result["prompt"]

    def test_compression_updates_ledger(self):
        messages = [
            {"role": "user", "content": "we will use deterministic compression"},
            {"role": "assistant", "content": "decided to skip AI summarization"},
        ]
        build_context("s1", messages)
        data = ledger.load("s1")
        # Compression should have extracted decisions into delta
        assert data["delta"] != ""

    def test_compression_detects_blockers(self):
        messages = [
            {"role": "user", "content": "I'm blocked on rate limit issues"},
        ]
        build_context("s1", messages)
        data = ledger.load("s1")
        assert len(data["blockers"]) > 0

    def test_compression_detects_open_questions(self):
        messages = [
            {"role": "user", "content": "should we use tiktoken for counting?"},
        ]
        build_context("s1", messages)
        data = ledger.load("s1")
        assert len(data["open"]) > 0

    def test_sigil_generation(self):
        messages = [
            {"role": "user", "content": "We forked to context_sov"},
        ]
        build_context("s1", messages)
        entries = sigil.load("s1")
        assert len(entries) > 0

    def test_token_estimate_positive(self):
        messages = [{"role": "user", "content": "hello"}]
        result = build_context("s1", messages)
        assert result["token_estimate"] > 0

    def test_window_shrinks_on_large_input(self, monkeypatch):
        # Set a very low token cap
        monkeypatch.setattr(token_gate, "MAX_TOKENS", 200)
        monkeypatch.setattr(token_gate, "LIVE_WINDOW", 16)

        # Create many messages to exceed budget
        messages = [
            {"role": "user", "content": f"This is message number {i} with some content"}
            for i in range(20)
        ]
        result = build_context("s1", messages)
        # Should succeed with a smaller window
        assert result["token_estimate"] <= 200

    def test_hard_fail_on_impossible_budget(self, monkeypatch):
        # Set impossibly low token cap
        monkeypatch.setattr(token_gate, "MAX_TOKENS", 5)
        monkeypatch.setattr(token_gate, "LIVE_WINDOW", 4)

        messages = [
            {"role": "user", "content": "x" * 1000},
        ]
        with pytest.raises(token_gate.TokenBudgetExceeded):
            build_context("s1", messages)

    def test_structured_content_blocks(self):
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Hello from structured content"},
                ],
            },
        ]
        result = build_context("s1", messages)
        assert "Hello from structured content" in result["prompt"]

    def test_no_md_history_injection(self):
        """Verify that build_context only uses provided messages, never reads .md files."""
        messages = [{"role": "user", "content": "just this"}]
        result = build_context("s1", messages)
        # The prompt should contain only our message content plus ledger/sigil structure
        assert "just this" in result["prompt"]
        # No markdown file references should appear
        assert ".md" not in result["prompt"]
