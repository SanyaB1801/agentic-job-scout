"""
Extracts numeric min/max from the free-text salary strings normalize.py
produces (e.g. "80000-120000 INR", "800000-1200000", "not listed").
Pure function, no deps, so it's trivially unit-testable.
"""
import re


def parse_salary(raw: str | None) -> tuple[int | None, int | None]:
    if not raw:
        return None, None
    nums = [int(n.replace(",", "")) for n in re.findall(r"[\d,]+", raw) if n.replace(",", "").isdigit()]
    if len(nums) >= 2:
        return min(nums[:2]), max(nums[:2])
    if len(nums) == 1:
        return nums[0], nums[0]
    return None, None