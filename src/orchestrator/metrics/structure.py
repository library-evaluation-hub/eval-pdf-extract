"""Structure metrics: table detection/cell F1, heading detection F1, reading order.

Implements the algorithms defined in contract/metric-spec.md §3.2.
"""

from __future__ import annotations

import math
from typing import Any

# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

Bbox = list[float]  # [x0, y0, x1, y1]


def iou(a: Bbox, b: Bbox) -> float:
    """Intersection-over-Union of two axis-aligned bounding boxes."""
    x0 = max(a[0], b[0])
    y0 = max(a[1], b[1])
    x1 = min(a[2], b[2])
    y1 = min(a[3], b[3])
    inter_w = max(0.0, x1 - x0)
    inter_h = max(0.0, y1 - y0)
    inter = inter_w * inter_h
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    if union <= 0:
        return 0.0
    return inter / union


def _greedy_match(
    detected: list[Bbox],
    ground_truth: list[Bbox],
    threshold: float = 0.5,
) -> list[tuple[int, int]]:
    """Greedy IoU matching. Returns list of (det_idx, gt_idx) pairs."""
    pairs: list[tuple[float, int, int]] = []
    for di, d in enumerate(detected):
        for gi, g in enumerate(ground_truth):
            score = iou(d, g)
            if score >= threshold:
                pairs.append((score, di, gi))
    # Sort by IoU descending — greedy best-first
    pairs.sort(key=lambda p: p[0], reverse=True)

    matched_d: set[int] = set()
    matched_g: set[int] = set()
    result: list[tuple[int, int]] = []
    for _, di, gi in pairs:
        if di in matched_d or gi in matched_g:
            continue
        matched_d.add(di)
        matched_g.add(gi)
        result.append((di, gi))
    return result


def _f1(tp: int, fp: int, fn: int) -> float:
    """Compute F1 from TP/FP/FN."""
    if tp == 0:
        return 0.0
    precision = tp / (tp + fp)
    recall = tp / (tp + fn)
    return 2 * precision * recall / (precision + recall)


# ---------------------------------------------------------------------------
# Table detection F1
# ---------------------------------------------------------------------------


def _collect_tables(pages: list[dict[str, Any]]) -> dict[int, list[Bbox]]:
    """Extract table bboxes per page_number."""
    result: dict[int, list[Bbox]] = {}
    for page in pages:
        pn = page.get("page_number", 0)
        tables = page.get("tables") or []
        result[pn] = [t["bbox"] for t in tables if "bbox" in t]
    return result


def table_detection_f1(
    result_pages: list[dict[str, Any]],
    expected_pages: list[dict[str, Any]],
) -> float | None:
    """F1 of table detection via bbox IoU >= 0.5.

    Returns None (skipped) if GT has no tables across all pages.
    """
    gt_tables = _collect_tables(expected_pages)
    total_gt = sum(len(v) for v in gt_tables.values())
    if total_gt == 0:
        return None  # skipped

    det_tables = _collect_tables(result_pages)

    all_pages = set(gt_tables.keys()) | set(det_tables.keys())
    f1_scores: list[float] = []
    for pn in all_pages:
        gts = gt_tables.get(pn, [])
        dets = det_tables.get(pn, [])
        if len(gts) == 0 and len(dets) == 0:
            continue
        matches = _greedy_match(dets, gts)
        tp = len(matches)
        fp = len(dets) - tp
        fn = len(gts) - tp
        f1_scores.append(_f1(tp, fp, fn))

    if not f1_scores:
        return 0.0
    return sum(f1_scores) / len(f1_scores)


# ---------------------------------------------------------------------------
# Table cell value F1
# ---------------------------------------------------------------------------


def _collect_tables_full(
    pages: list[dict[str, Any]],
) -> dict[int, list[dict[str, Any]]]:
    """Extract full table objects per page_number."""
    result: dict[int, list[dict[str, Any]]] = {}
    for page in pages:
        pn = page.get("page_number", 0)
        tables = page.get("tables") or []
        result[pn] = tables
    return result


def table_cell_value_f1(
    result_pages: list[dict[str, Any]],
    expected_pages: list[dict[str, Any]],
) -> float | None:
    """F1 of cell values in correctly detected tables.

    Returns None (skipped) if GT has no tables.
    """
    gt_full = _collect_tables_full(expected_pages)
    total_gt = sum(len(v) for v in gt_full.values())
    if total_gt == 0:
        return None  # skipped

    det_full = _collect_tables_full(result_pages)

    all_pages = set(gt_full.keys()) | set(det_full.keys())
    f1_scores: list[float] = []
    for pn in all_pages:
        gts = gt_full.get(pn, [])
        dets = det_full.get(pn, [])
        if len(gts) == 0:
            continue
        # Match tables by IoU
        det_bboxes = [t.get("bbox", [0, 0, 0, 0]) for t in dets]
        gt_bboxes = [t.get("bbox", [0, 0, 0, 0]) for t in gts]
        matches = _greedy_match(det_bboxes, gt_bboxes)

        if not matches:
            f1_scores.append(0.0)
            continue

        # Build cell key sets for matched tables
        det_cells: set[tuple[int, int, int, str]] = set()
        gt_cells: set[tuple[int, int, int, str]] = set()

        for match_idx, (di, gi) in enumerate(matches):
            det_table = dets[di]
            gt_table = gts[gi]
            det_rows = det_table.get("rows") or []
            gt_rows = gt_table.get("rows") or []
            max_rows = max(len(det_rows), len(gt_rows))
            for r in range(max_rows):
                det_row = det_rows[r] if r < len(det_rows) else []
                gt_row = gt_rows[r] if r < len(gt_rows) else []
                max_cols = max(len(det_row), len(gt_row))
                for c in range(max_cols):
                    det_val = det_row[c] if c < len(det_row) else ""
                    gt_val = gt_row[c] if c < len(gt_row) else ""
                    det_cells.add((match_idx, r, c, det_val))
                    gt_cells.add((match_idx, r, c, gt_val))

        # F1 on exact-match cells
        tp = len(det_cells & gt_cells)
        fp = len(det_cells - gt_cells)
        fn = len(gt_cells - det_cells)
        f1_scores.append(_f1(tp, fp, fn))

    if not f1_scores:
        return 0.0
    return sum(f1_scores) / len(f1_scores)


# ---------------------------------------------------------------------------
# Heading detection F1
# ---------------------------------------------------------------------------


def _collect_heading_bboxes(pages: list[dict[str, Any]]) -> dict[int, list[Bbox]]:
    """Extract heading block bboxes per page_number."""
    result: dict[int, list[Bbox]] = {}
    for page in pages:
        pn = page.get("page_number", 0)
        blocks = page.get("blocks") or []
        result[pn] = [
            b["bbox"]
            for b in blocks
            if b.get("type") == "heading" and "bbox" in b
        ]
    return result


def heading_detection_f1(
    result_pages: list[dict[str, Any]],
    expected_pages: list[dict[str, Any]],
) -> float | None:
    """F1 of heading detection via bbox IoU >= 0.5.

    Returns None (skipped) if GT has no headings.
    """
    gt_headings = _collect_heading_bboxes(expected_pages)
    total_gt = sum(len(v) for v in gt_headings.values())
    if total_gt == 0:
        return None  # skipped

    det_headings = _collect_heading_bboxes(result_pages)

    all_pages = set(gt_headings.keys()) | set(det_headings.keys())
    f1_scores: list[float] = []
    for pn in all_pages:
        gts = gt_headings.get(pn, [])
        dets = det_headings.get(pn, [])
        if len(gts) == 0 and len(dets) == 0:
            continue
        matches = _greedy_match(dets, gts)
        tp = len(matches)
        fp = len(dets) - tp
        fn = len(gts) - tp
        f1_scores.append(_f1(tp, fp, fn))

    if not f1_scores:
        return 0.0
    return sum(f1_scores) / len(f1_scores)


# ---------------------------------------------------------------------------
# Reading order Kendall's tau-b
# ---------------------------------------------------------------------------


def _collect_blocks_with_bbox(
    pages: list[dict[str, Any]],
) -> dict[int, list[dict[str, Any]]]:
    """Extract blocks (with bbox + reading_order) per page_number."""
    result: dict[int, list[dict[str, Any]]] = {}
    for page in pages:
        pn = page.get("page_number", 0)
        blocks = page.get("blocks") or []
        result[pn] = [b for b in blocks if "bbox" in b and "reading_order" in b]
    return result


def kendall_tau_b(rank1: list[int], rank2: list[int]) -> float:
    """Kendall's tau-b rank correlation coefficient.

    Handles ties in either ranking. Returns value in [-1, 1].
    """
    n = len(rank1)
    if n < 2:
        return 1.0 if n == 1 else 0.0  # vacuous for 0 or 1 element

    concordant = 0
    discordant = 0
    ties_a = 0  # tied only in rank1
    ties_b = 0  # tied only in rank2
    ties_both = 0  # tied in both rankings

    for i in range(n):
        for j in range(i + 1, n):
            a = rank1[i] - rank1[j]
            b = rank2[i] - rank2[j]
            ab = a * b
            if ab > 0:
                concordant += 1
            elif ab < 0:
                discordant += 1
            else:
                # At least one tie
                if a == 0 and b == 0:
                    ties_both += 1
                elif a == 0:
                    ties_a += 1
                else:
                    ties_b += 1

    # tau-b denominator: (C + D + ties_b_only) * (C + D + ties_a_only)
    # ties_both is excluded from each factor since it's not a tie in
    # just one ranking
    denom = math.sqrt(
        (concordant + discordant + ties_b)
        * (concordant + discordant + ties_a)
    )
    if denom == 0:
        return 0.0
    return (concordant - discordant) / denom


def reading_order_kendall_tau(
    result_pages: list[dict[str, Any]],
    expected_pages: list[dict[str, Any]],
) -> float | None:
    """Kendall's tau-b of reading_order sequences for matched blocks.

    Blocks are matched by bbox IoU >= 0.5. Returns None (skipped) if
    no pages have blocks.
    """
    det_blocks = _collect_blocks_with_bbox(result_pages)
    gt_blocks = _collect_blocks_with_bbox(expected_pages)

    all_pages = set(gt_blocks.keys()) | set(det_blocks.keys())
    tau_scores: list[float] = []

    for pn in all_pages:
        gts = gt_blocks.get(pn, [])
        dets = det_blocks.get(pn, [])
        if len(gts) == 0 or len(dets) == 0:
            continue

        # Match blocks by IoU
        det_bboxes = [b["bbox"] for b in dets]
        gt_bboxes = [b["bbox"] for b in gts]
        matches = _greedy_match(det_bboxes, gt_bboxes)

        if len(matches) < 2:
            # Need at least 2 matched blocks for meaningful tau
            if len(matches) == 1:
                tau_scores.append(1.0)  # single block trivially correct
            continue

        # Extract reading_order sequences for matched pairs
        det_orders = [dets[di].get("reading_order", 0) for di, gi in matches]
        gt_orders = [gts[gi].get("reading_order", 0) for di, gi in matches]

        tau_scores.append(kendall_tau_b(det_orders, gt_orders))

    if not tau_scores:
        return None  # skipped

    return sum(tau_scores) / len(tau_scores)
