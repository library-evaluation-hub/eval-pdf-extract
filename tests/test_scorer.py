"""Unit tests for scorer: score() with known input/output, skipped metrics,
zero-page edge case, invalid result handling."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from orchestrator.models import RunResult
from orchestrator.scorer import score
from tests.conftest import make_block, make_page, make_result, make_table


def _expected_with_pages(pages: list[dict[str, Any]]) -> dict[str, Any]:
    """Build an expected.json dict with given pages."""
    return make_result(pages)


class TestScorePerfectMatch:
    def test_identical_single_page(self, make_run_result: Callable[..., RunResult]) -> None:
        page = make_page(1, text="Hello World", blocks=[
            make_block("b0", "paragraph", [0, 0, 100, 20], "Hello World", reading_order=0),
        ])
        expected = _expected_with_pages([page])
        rr = make_run_result(result_data=make_result([page]))

        sr = score(rr, expected, "plain_text")

        assert sr.metrics["success"] is True
        assert sr.metrics["text_cer"] == 0.0
        assert sr.metrics["text_wer"] == 0.0
        assert sr.metrics["text_exact_page_match_ratio"] == 1.0
        assert sr.metrics["error_category"] == "none"
        assert sr.metrics["partial_completion_ratio"] == 1.0
        # structure metrics: no tables/headings in GT → skipped
        assert "table_detection_f1" in sr.skipped_metrics
        assert "heading_detection_f1" in sr.skipped_metrics

    def test_identical_multi_page(self, make_run_result: Callable[..., RunResult]) -> None:
        pages = [
            make_page(1, text="Page one content"),
            make_page(2, text="Page two content"),
        ]
        expected = _expected_with_pages(pages)
        rr = make_run_result(result_data=make_result(pages))

        sr = score(rr, expected, "plain_text")

        assert sr.metrics["text_cer"] == 0.0
        assert sr.metrics["text_wer"] == 0.0
        assert sr.metrics["text_exact_page_match_ratio"] == 1.0


class TestScoreTextMismatch:
    def test_one_char_diff(self, make_run_result: Callable[..., RunResult]) -> None:
        gt_page = make_page(1, text="hello world")
        det_page = make_page(1, text="hello worlt")
        expected = _expected_with_pages([gt_page])
        rr = make_run_result(result_data=make_result([det_page]))

        sr = score(rr, expected, "plain_text")

        assert sr.metrics["text_cer"] is not None
        assert sr.metrics["text_cer"] > 0.0
        assert sr.metrics["text_exact_page_match_ratio"] == 0.0

    def test_missing_page_in_result(self, make_run_result: Callable[..., RunResult]) -> None:
        gt_pages = [make_page(1, text="page1"), make_page(2, text="page2")]
        det_pages = [make_page(1, text="page1")]
        expected = _expected_with_pages(gt_pages)
        rr = make_run_result(result_data=make_result(det_pages))

        sr = score(rr, expected, "plain_text")

        # 1 exact match out of 2 total pages
        assert sr.metrics["text_exact_page_match_ratio"] == 0.5

    def test_extra_page_in_result(self, make_run_result: Callable[..., RunResult]) -> None:
        gt_pages = [make_page(1, text="page1")]
        det_pages = [make_page(1, text="page1"), make_page(2, text="extra")]
        expected = _expected_with_pages(gt_pages)
        rr = make_run_result(result_data=make_result(det_pages))

        sr = score(rr, expected, "plain_text")

        # 1 exact match out of 2 total pages
        assert sr.metrics["text_exact_page_match_ratio"] == 0.5


class TestScoreInvalidResult:
    def test_no_result_data(self, make_run_result: Callable[..., RunResult]) -> None:
        expected = _expected_with_pages([make_page(1, text="hello")])
        rr = make_run_result(
            result_data=None,
            result_valid=False,
            has_result=False,
            exit_code=1,
            error_category="crash",
        )

        sr = score(rr, expected, "plain_text")

        assert sr.metrics["success"] is False
        assert sr.metrics["error_category"] == "crash"
        # text/structure metrics should be skipped
        assert "text_cer" in sr.skipped_metrics
        assert "table_detection_f1" in sr.skipped_metrics
        assert sr.metrics["text_cer"] is None


class TestScoreZeroPage:
    def test_both_zero_pages(self, make_run_result: Callable[..., RunResult]) -> None:
        expected = _expected_with_pages([])
        rr = make_run_result(result_data=make_result([]))

        sr = score(rr, expected, "plain_text")

        assert sr.metrics["success"] is True
        assert sr.metrics["text_cer"] == 0.0
        assert sr.metrics["text_wer"] == 0.0
        assert sr.metrics["text_exact_page_match_ratio"] == 1.0

    def test_zero_expected_nonzero_result(self, make_run_result: Callable[..., RunResult]) -> None:
        expected = _expected_with_pages([])
        rr = make_run_result(result_data=make_result([make_page(1, text="extra")]))

        sr = score(rr, expected, "plain_text")

        assert sr.metrics["success"] is False
        assert sr.metrics["text_cer"] == 1.0
        assert sr.metrics["text_wer"] == 1.0
        assert sr.metrics["text_exact_page_match_ratio"] == 0.0


class TestScoreStructureMetrics:
    def test_table_metrics_computed(self, make_run_result: Callable[..., RunResult]) -> None:
        t = make_table([10, 10, 100, 50], [["a", "b"]])
        page = make_page(1, text="a b", tables=[t])
        expected = _expected_with_pages([page])
        rr = make_run_result(result_data=make_result([page]))

        sr = score(rr, expected, "table")

        assert sr.metrics["table_detection_f1"] is not None
        assert sr.metrics["table_detection_f1"] == 1.0
        assert sr.metrics["table_cell_value_f1"] is not None
        assert sr.metrics["table_cell_value_f1"] == 1.0
        assert "table_detection_f1" not in sr.skipped_metrics

    def test_heading_metrics_computed(self, make_run_result: Callable[..., RunResult]) -> None:
        h = make_block("b0", "heading", [0, 0, 100, 30], "Title", level=1)
        page = make_page(1, text="Title", blocks=[h])
        expected = _expected_with_pages([page])
        rr = make_run_result(result_data=make_result([page]))

        sr = score(rr, expected, "plain_text")

        assert sr.metrics["heading_detection_f1"] is not None
        assert sr.metrics["heading_detection_f1"] == 1.0
        assert "heading_detection_f1" not in sr.skipped_metrics
