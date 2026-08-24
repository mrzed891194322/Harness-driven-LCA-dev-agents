from __future__ import annotations


def next_lci_review_action(attempt: int, passed: bool) -> str:
    """Return the only legal action after an LCI review attempt."""
    if isinstance(attempt, bool) or not isinstance(attempt, int) or not 1 <= attempt <= 3:
        raise ValueError("attempt must be an integer from 1 through 3")
    if passed:
        return "proceed_to_preflight"
    if attempt < 3:
        return "targeted_fix_and_review"
    return "stop_failed"
