"""Unit tests for text metrics: normalize_text, levenshtein, cer, wer, exact_page_match."""

from __future__ import annotations

from orchestrator.metrics.text import (
    cer,
    exact_page_match,
    levenshtein,
    levenshtein_tokens,
    normalize_text,
    wer,
)


class TestNormalizeText:
    def test_strips_whitespace(self) -> None:
        assert normalize_text("  hello  world  ") == "hello world"

    def test_merges_consecutive_whitespace(self) -> None:
        assert normalize_text("a\n\nb\t\tc") == "a b c"

    def test_standardizes_quotes(self) -> None:
        assert normalize_text("\u201chello\u201d") == '"hello"'
        assert normalize_text("\u2018hi\u2019") == "'hi'"

    def test_standardizes_dashes(self) -> None:
        assert normalize_text("a\u2014b") == "a-b"
        assert normalize_text("a\u2013b") == "a-b"

    def test_empty_string(self) -> None:
        assert normalize_text("") == ""

    def test_only_whitespace(self) -> None:
        assert normalize_text("   \n\t  ") == ""


class TestLevenshtein:
    def test_identical_strings(self) -> None:
        assert levenshtein("hello", "hello") == 0

    def test_one_substitution(self) -> None:
        assert levenshtein("hello", "hallo") == 1

    def test_one_insertion(self) -> None:
        assert levenshtein("hello", "helloo") == 1

    def test_one_deletion(self) -> None:
        assert levenshtein("hello", "helo") == 1

    def test_empty_string(self) -> None:
        assert levenshtein("", "abc") == 3
        assert levenshtein("abc", "") == 3
        assert levenshtein("", "") == 0

    def test_completely_different(self) -> None:
        assert levenshtein("abc", "xyz") == 3


class TestLevenshteinTokens:
    def test_identical_tokens(self) -> None:
        assert levenshtein_tokens(["a", "b"], ["a", "b"]) == 0

    def test_one_substitution(self) -> None:
        assert levenshtein_tokens(["a", "b"], ["a", "c"]) == 1

    def test_empty_lists(self) -> None:
        assert levenshtein_tokens([], ["a"]) == 1
        assert levenshtein_tokens([], []) == 0


class TestCER:
    def test_identical_text(self) -> None:
        assert cer("hello world", "hello world") == 0.0

    def test_one_char_diff(self) -> None:
        # 1 substitution out of 11 chars
        assert abs(cer("hello world", "hello worlt") - 1 / 11) < 1e-9

    def test_completely_different(self) -> None:
        assert cer("abc", "xyz") == 1.0

    def test_empty_ref_empty_hyp(self) -> None:
        assert cer("", "") == 0.0

    def test_empty_ref_nonempty_hyp(self) -> None:
        assert cer("", "abc") == 1.0

    def test_nonempty_ref_empty_hyp(self) -> None:
        assert cer("abc", "") == 1.0

    def test_cer_exceeds_1(self) -> None:
        # levenshtein("a", "abcde") = 4, len("a") = 1 → CER = 4.0
        # CER is not capped at 1.0
        assert abs(cer("a", "abcde") - 4.0) < 1e-9

    def test_normalization_applied(self) -> None:
        # curly quotes should be normalized before comparison
        assert cer("\u201chello\u201d", '"hello"') == 0.0


class TestWER:
    def test_identical_text(self) -> None:
        assert wer("hello world", "hello world") == 0.0

    def test_one_word_substitution(self) -> None:
        # 1 substitution out of 2 words
        assert abs(wer("hello world", "hello earth") - 0.5) < 1e-9

    def test_one_word_insertion(self) -> None:
        # 1 insertion out of 2 ref words
        assert abs(wer("hello world", "hello world foo") - 0.5) < 1e-9

    def test_empty_ref_empty_hyp(self) -> None:
        assert wer("", "") == 0.0

    def test_empty_ref_nonempty_hyp(self) -> None:
        assert wer("", "abc") == 1.0

    def test_normalization_applied(self) -> None:
        assert wer("hello   world", "hello world") == 0.0


class TestExactPageMatch:
    def test_exact_match(self) -> None:
        assert exact_page_match("hello world", "hello world") is True

    def test_match_after_normalization(self) -> None:
        assert exact_page_match("  hello   world  ", "hello world") is True

    def test_no_match(self) -> None:
        assert exact_page_match("hello world", "hello earth") is False

    def test_both_empty(self) -> None:
        assert exact_page_match("", "") is True

    def test_quote_normalization(self) -> None:
        assert exact_page_match("\u201chello\u201d", '"hello"') is True
