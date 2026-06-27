"""Unit tests for robustness metrics: classify_exit_code, compute_success,
partial_completion_ratio."""

from __future__ import annotations

from orchestrator.metrics.robustness import (
    classify_exit_code,
    compute_success,
    partial_completion_ratio,
)


class TestClassifyExitCode:
    def test_success(self) -> None:
        assert classify_exit_code(0, True) == "none"

    def test_bad_args(self) -> None:
        assert classify_exit_code(2, False) == "bad_args"

    def test_unsupported(self) -> None:
        assert classify_exit_code(64, False) == "unsupported"

    def test_parse_error(self) -> None:
        assert classify_exit_code(65, False) == "parse_error"

    def test_oom(self) -> None:
        assert classify_exit_code(66, False) == "oom"

    def test_timeout(self) -> None:
        assert classify_exit_code(124, False) == "timeout"

    def test_unknown_exit_code(self) -> None:
        assert classify_exit_code(1, False) == "crash"
        assert classify_exit_code(137, False) == "crash"


class TestComputeSuccess:
    def test_full_success(self) -> None:
        assert compute_success(
            exit_code=0, has_result=True, result_valid=True,
            result_page_count=3, expected_page_count=3,
        ) is True

    def test_nonzero_exit(self) -> None:
        assert compute_success(
            exit_code=1, has_result=True, result_valid=True,
            result_page_count=3, expected_page_count=3,
        ) is False

    def test_no_result(self) -> None:
        assert compute_success(
            exit_code=0, has_result=False, result_valid=False,
            result_page_count=0, expected_page_count=3,
        ) is False

    def test_invalid_result(self) -> None:
        assert compute_success(
            exit_code=0, has_result=True, result_valid=False,
            result_page_count=3, expected_page_count=3,
        ) is False

    def test_page_count_mismatch(self) -> None:
        assert compute_success(
            exit_code=0, has_result=True, result_valid=True,
            result_page_count=2, expected_page_count=3,
        ) is False

    def test_zero_pages_both(self) -> None:
        assert compute_success(
            exit_code=0, has_result=True, result_valid=True,
            result_page_count=0, expected_page_count=0,
        ) is True


class TestPartialCompletionRatio:
    def test_full_completion(self) -> None:
        assert partial_completion_ratio(3, 3) == 1.0

    def test_partial(self) -> None:
        assert abs(partial_completion_ratio(2, 4) - 0.5) < 1e-9

    def test_over_complete(self) -> None:
        # capped at 1.0
        assert partial_completion_ratio(5, 3) == 1.0

    def test_zero_expected_zero_result(self) -> None:
        assert partial_completion_ratio(0, 0) == 1.0

    def test_zero_expected_nonzero_result(self) -> None:
        assert partial_completion_ratio(3, 0) == 0.0

    def test_no_completion(self) -> None:
        assert partial_completion_ratio(0, 5) == 0.0
