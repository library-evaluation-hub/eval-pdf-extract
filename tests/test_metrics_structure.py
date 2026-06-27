"""Unit tests for structure metrics: iou, table_detection_f1, table_cell_value_f1,
heading_detection_f1, kendall_tau_b, reading_order_kendall_tau."""

from __future__ import annotations

from tests.conftest import make_block, make_page, make_table

from orchestrator.metrics.structure import (
    heading_detection_f1,
    iou,
    kendall_tau_b,
    reading_order_kendall_tau,
    table_cell_value_f1,
    table_detection_f1,
)


class TestIoU:
    def test_identical_boxes(self) -> None:
        assert iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1.0

    def test_no_overlap(self) -> None:
        assert iou([0, 0, 10, 10], [20, 20, 30, 30]) == 0.0

    def test_partial_overlap(self) -> None:
        # a = 100, b = 100, inter = 25, union = 175
        result = iou([0, 0, 10, 10], [5, 5, 15, 15])
        assert abs(result - 25 / 175) < 1e-9

    def test_one_inside_other(self) -> None:
        # a = 100, b = 25, inter = 25, union = 100
        result = iou([0, 0, 10, 10], [2, 2, 7, 7])
        assert abs(result - 25 / 100) < 1e-9

    def test_zero_area_boxes(self) -> None:
        assert iou([0, 0, 0, 0], [0, 0, 10, 10]) == 0.0


class TestTableDetectionF1:
    def test_no_tables_in_gt(self) -> None:
        gt = [make_page(1)]
        det = [make_page(1)]
        assert table_detection_f1(det, gt) is None

    def test_perfect_detection(self) -> None:
        t = make_table([10, 10, 100, 50], [["a", "b"]])
        gt = [make_page(1, tables=[t])]
        det = [make_page(1, tables=[t])]
        result = table_detection_f1(det, gt)
        assert result is not None
        assert abs(result - 1.0) < 1e-9

    def test_missed_table(self) -> None:
        t = make_table([10, 10, 100, 50], [["a"]])
        gt = [make_page(1, tables=[t])]
        det = [make_page(1, tables=[])]
        result = table_detection_f1(det, gt)
        assert result is not None
        assert abs(result - 0.0) < 1e-9

    def test_false_positive(self) -> None:
        t = make_table([10, 10, 100, 50], [["a"]])
        gt = [make_page(1, tables=[t])]
        det = [make_page(1, tables=[
            make_table([10, 10, 100, 50], [["a"]]),
            make_table([200, 200, 300, 250], [["b"]]),
        ])]
        result = table_detection_f1(det, gt)
        assert result is not None
        # tp=1, fp=1, fn=0 → precision=0.5, recall=1.0 → f1=2/3
        assert abs(result - 2 / 3) < 1e-9


class TestTableCellValueF1:
    def test_no_tables_in_gt(self) -> None:
        gt = [make_page(1)]
        det = [make_page(1)]
        assert table_cell_value_f1(det, gt) is None

    def test_perfect_cells(self) -> None:
        t = make_table([10, 10, 100, 50], [["a", "b"], ["c", "d"]])
        gt = [make_page(1, tables=[t])]
        det = [make_page(1, tables=[t])]
        result = table_cell_value_f1(det, gt)
        assert result is not None
        assert abs(result - 1.0) < 1e-9

    def test_wrong_cell_values(self) -> None:
        gt_t = make_table([10, 10, 100, 50], [["a", "b"], ["c", "d"]])
        det_t = make_table([10, 10, 100, 50], [["a", "x"], ["c", "d"]])
        gt = [make_page(1, tables=[gt_t])]
        det = [make_page(1, tables=[det_t])]
        result = table_cell_value_f1(det, gt)
        assert result is not None
        # tp=3, fp=1, fn=1 → precision=0.75, recall=0.75 → f1=0.75
        assert abs(result - 0.75) < 1e-9


class TestHeadingDetectionF1:
    def test_no_headings_in_gt(self) -> None:
        gt = [make_page(1, blocks=[
            make_block("b1", "paragraph", [0, 0, 100, 20], "text"),
        ])]
        det = [make_page(1, blocks=[
            make_block("b1", "paragraph", [0, 0, 100, 20], "text"),
        ])]
        assert heading_detection_f1(det, gt) is None

    def test_perfect_detection(self) -> None:
        h = make_block("b1", "heading", [0, 0, 100, 30], "Title", level=1)
        gt = [make_page(1, blocks=[h])]
        det = [make_page(1, blocks=[h])]
        result = heading_detection_f1(det, gt)
        assert result is not None
        assert abs(result - 1.0) < 1e-9

    def test_missed_heading(self) -> None:
        h = make_block("b1", "heading", [0, 0, 100, 30], "Title", level=1)
        gt = [make_page(1, blocks=[h])]
        det = [make_page(1, blocks=[])]
        result = heading_detection_f1(det, gt)
        assert result is not None
        assert abs(result - 0.0) < 1e-9


class TestKendallTauB:
    def test_identical_rankings(self) -> None:
        assert abs(kendall_tau_b([1, 2, 3, 4], [1, 2, 3, 4]) - 1.0) < 1e-9

    def test_reversed_rankings(self) -> None:
        assert abs(kendall_tau_b([1, 2, 3, 4], [4, 3, 2, 1]) - (-1.0)) < 1e-9

    def test_single_element(self) -> None:
        assert kendall_tau_b([1], [1]) == 1.0

    def test_empty_lists(self) -> None:
        assert kendall_tau_b([], []) == 0.0

    def test_ties_in_both(self) -> None:
        # All tied → denom = 0 → return 0.0
        assert kendall_tau_b([1, 1, 1], [1, 1, 1]) == 0.0

    def test_partial_correlation(self) -> None:
        # 4 pairs: (1,1), (2,3), (3,2), (4,4)
        # concordant: (1,2)(a>0,b>0), (1,3), (1,4), (2,4)(a>0,b>0), (3,4)
        # discordant: (2,3)(a<0,b>0)
        # Actually let me compute properly:
        # pairs: (0,1): a=1-2=-1, b=1-3=-2, ab=2 >0 → concordant
        # (0,2): a=1-3=-2, b=1-2=-1, ab=2 >0 → concordant
        # (0,3): a=1-4=-3, b=1-4=-3, ab=9 >0 → concordant
        # (1,2): a=2-3=-1, b=3-2=1, ab=-1 <0 → discordant
        # (1,3): a=2-4=-2, b=3-4=-1, ab=2 >0 → concordant
        # (2,3): a=3-4=-1, b=2-4=-2, ab=2 >0 → concordant
        # C=5, D=1, ties_a=0, ties_b=0
        # tau = (5-1)/sqrt((5+1)*(5+1)) = 4/6
        result = kendall_tau_b([1, 2, 3, 4], [1, 3, 2, 4])
        assert abs(result - 4 / 6) < 1e-9


class TestReadingOrderKendallTau:
    def test_no_blocks(self) -> None:
        gt = [make_page(1)]
        det = [make_page(1)]
        assert reading_order_kendall_tau(det, gt) is None

    def test_perfect_order(self) -> None:
        blocks = [
            make_block("b0", "paragraph", [0, 0, 100, 20], "a", reading_order=0),
            make_block("b1", "paragraph", [0, 30, 100, 50], "b", reading_order=1),
            make_block("b2", "paragraph", [0, 60, 100, 80], "c", reading_order=2),
        ]
        gt = [make_page(1, blocks=blocks)]
        det = [make_page(1, blocks=blocks)]
        result = reading_order_kendall_tau(det, gt)
        assert result is not None
        assert abs(result - 1.0) < 1e-9

    def test_reversed_order(self) -> None:
        gt_blocks = [
            make_block("b0", "paragraph", [0, 0, 100, 20], "a", reading_order=0),
            make_block("b1", "paragraph", [0, 30, 100, 50], "b", reading_order=1),
            make_block("b2", "paragraph", [0, 60, 100, 80], "c", reading_order=2),
        ]
        det_blocks = [
            make_block("b0", "paragraph", [0, 0, 100, 20], "a", reading_order=2),
            make_block("b1", "paragraph", [0, 30, 100, 50], "b", reading_order=1),
            make_block("b2", "paragraph", [0, 60, 100, 80], "c", reading_order=0),
        ]
        gt = [make_page(1, blocks=gt_blocks)]
        det = [make_page(1, blocks=det_blocks)]
        result = reading_order_kendall_tau(det, gt)
        assert result is not None
        assert abs(result - (-1.0)) < 1e-9

    def test_single_block(self) -> None:
        blocks = [make_block("b0", "paragraph", [0, 0, 100, 20], "a", reading_order=0)]
        gt = [make_page(1, blocks=blocks)]
        det = [make_page(1, blocks=blocks)]
        result = reading_order_kendall_tau(det, gt)
        assert result is not None
        assert abs(result - 1.0) < 1e-9
