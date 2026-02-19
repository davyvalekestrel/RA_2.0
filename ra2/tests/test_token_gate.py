"""Tests for ra2.token_gate"""

import pytest
from ra2.token_gate import (
    estimate_tokens,
    check_budget,
    shrink_window,
    TokenBudgetExceeded,
    LIVE_WINDOW_MIN,
)


class TestEstimateTokens:
    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_short_string(self):
        # "ab" = 2 chars, 2//4 = 0 → clamped to 1
        assert estimate_tokens("ab") == 1

    def test_known_length(self):
        text = "a" * 400
        # 400 / 4 = 100
        assert estimate_tokens(text) == 100

    def test_proportional(self):
        short = estimate_tokens("hello world")
        long = estimate_tokens("hello world " * 100)
        assert long > short


class TestCheckBudget:
    def test_within_budget(self):
        assert check_budget(100, limit=200) is True

    def test_at_budget(self):
        assert check_budget(200, limit=200) is True

    def test_over_budget(self):
        assert check_budget(201, limit=200) is False


class TestShrinkWindow:
    def test_halves(self):
        assert shrink_window(16) == 8

    def test_halves_again(self):
        assert shrink_window(8) == 4

    def test_at_minimum_raises(self):
        with pytest.raises(TokenBudgetExceeded):
            shrink_window(LIVE_WINDOW_MIN)

    def test_below_minimum_raises(self):
        with pytest.raises(TokenBudgetExceeded):
            shrink_window(2)

    def test_odd_number(self):
        # 5 // 2 = 2, but clamped to LIVE_WINDOW_MIN (4)
        assert shrink_window(5) == LIVE_WINDOW_MIN


class TestTokenBudgetExceeded:
    def test_attributes(self):
        exc = TokenBudgetExceeded(estimated=7000, limit=6000)
        assert exc.estimated == 7000
        assert exc.limit == 6000
        assert "7000" in str(exc)
        assert "6000" in str(exc)
