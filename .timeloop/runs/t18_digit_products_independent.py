#!/usr/bin/env python3
"""Independent recheck of T18 without importing the discovery kernel."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def transcribed_step(n: int, base: int) -> int:
    if n == 0:
        return 0
    product = 1
    total = 0
    while n:
        n, digit = divmod(n, base)
        product *= digit
        total += digit
    return product + total


def transcribed_bound(base: int) -> int:
    width = 1
    while True:
        maximum = (base - 1) ** width + width * (base - 1)
        if maximum < base ** (width - 1):
            return maximum
        width += 1


def canonical(values: list[int]) -> tuple[int, ...]:
    least_value = min(values)
    least_index = values.index(least_value)
    return tuple(values[least_index:] + values[:least_index])


def transcribed_cycles(base: int, bound: int) -> set[tuple[int, ...]]:
    status = bytearray(bound + 1)
    found: set[tuple[int, ...]] = set()
    for start in range(bound + 1):
        if status[start]:
            continue
        positions: dict[int, int] = {}
        path: list[int] = []
        value = start
        while status[value] == 0 and value not in positions:
            positions[value] = len(path)
            path.append(value)
            value = transcribed_step(value, base)
        if value in positions:
            found.add(canonical(path[positions[value] :]))
        for visited in path:
            status[visited] = 1
    return found


def recorded_cycles(payload: dict[str, object], base: int) -> set[tuple[int, ...]]:
    cycle_map = payload["cycles"]
    if not isinstance(cycle_map, dict):
        raise TypeError("cycles must be an object")
    entries = cycle_map[str(base)]
    if not isinstance(entries, list):
        raise TypeError("cycle entries must be a list")
    result: set[tuple[int, ...]] = set()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("values"), list):
            raise TypeError("cycle entry must contain values")
        result.add(tuple(int(value) for value in entry["values"]))
    return result


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {Path(sys.argv[0]).name} RESULTS.json")
    payload = json.loads(Path(sys.argv[1]).read_text())
    bases = payload.get("bases")
    bounds = payload.get("bounds")
    if not isinstance(bases, list) or not isinstance(bounds, dict):
        raise TypeError("results must contain bases and bounds")
    for raw_base in bases:
        base = int(raw_base)
        recorded_bound = int(bounds[str(base)])
        independent_bound = transcribed_bound(base)
        if recorded_bound != independent_bound:
            raise SystemExit(
                f"FAIL base={base} bound recorded={recorded_bound} "
                f"independent={independent_bound}"
            )
        expected = recorded_cycles(payload, base)
        actual = transcribed_cycles(base, independent_bound)
        if expected != actual:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            raise SystemExit(f"FAIL base={base} missing={missing} extra={extra}")
        print(
            f"PASS base={base} states=0..{independent_bound} "
            f"cycles={len(actual)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
