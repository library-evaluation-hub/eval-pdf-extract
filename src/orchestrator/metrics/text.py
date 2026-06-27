"""Text accuracy metrics: CER, WER, exact page match.

Implements the algorithms defined in contract/metric-spec.md §3.1.
"""

from __future__ import annotations

import re

# Characters to normalize for quote/dash standardization
_QUOTE_MAP: dict[str, str] = {
    "\u201c": '"',  # left double quote
    "\u201d": '"',  # right double quote
    "\u2018": "'",  # left single quote
    "\u2019": "'",  # right single quote
    "\u2014": "-",  # em dash
    "\u2013": "-",  # en dash
}


def normalize_text(text: str) -> str:
    """Normalize text: merge whitespace, strip, standardize quotes/dashes."""
    # Standardize quotes and dashes
    for orig, repl in _QUOTE_MAP.items():
        text = text.replace(orig, repl)
    # Merge consecutive whitespace into single space
    text = re.sub(r"\s+", " ", text)
    # Strip leading/trailing whitespace
    return text.strip()


def levenshtein(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def levenshtein_tokens(t1: list[str], t2: list[str]) -> int:
    """Compute Levenshtein edit distance between two token lists."""
    if len(t1) < len(t2):
        return levenshtein_tokens(t2, t1)
    if len(t2) == 0:
        return len(t1)
    previous_row = list(range(len(t2) + 1))
    for i, w1 in enumerate(t1):
        current_row = [i + 1]
        for j, w2 in enumerate(t2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (w1 != w2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def cer(reference: str, hypothesis: str) -> float:
    """Character Error Rate.

    cer = levenshtein(ref, hyp) / len(ref)
    If reference is empty: 0.0 if hypothesis is also empty, else 1.0.
    """
    ref = normalize_text(reference)
    hyp = normalize_text(hypothesis)
    if len(ref) == 0:
        return 0.0 if len(hyp) == 0 else 1.0
    return levenshtein(ref, hyp) / len(ref)


def wer(reference: str, hypothesis: str) -> float:
    """Word Error Rate.

    wer = levenshtein_tokens(ref_tokens, hyp_tokens) / len(ref_tokens)
    If reference is empty: 0.0 if hypothesis is also empty, else 1.0.
    """
    ref = normalize_text(reference)
    hyp = normalize_text(hypothesis)
    ref_tokens = ref.split()
    hyp_tokens = hyp.split()
    if len(ref_tokens) == 0:
        return 0.0 if len(hyp_tokens) == 0 else 1.0
    return levenshtein_tokens(ref_tokens, hyp_tokens) / len(ref_tokens)


def exact_page_match(reference: str, hypothesis: str) -> bool:
    """Check if normalized text matches exactly (char-by-char)."""
    return normalize_text(reference) == normalize_text(hypothesis)
