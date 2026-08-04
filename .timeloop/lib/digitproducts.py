"""Finite dynamics for the digit-product-plus-sum map."""

from __future__ import annotations

from math import prod
from typing import Callable


def digits(n: int, base: int) -> tuple[int, ...]:
    if n < 0:
        raise ValueError("n must be nonnegative")
    if base < 2:
        raise ValueError("base must be at least 2")
    if n == 0:
        return (0,)
    out: list[int] = []
    while n:
        out.append(n % base)
        n //= base
    return tuple(out)


def product_plus_sum_step(n: int, base: int) -> int:
    ds = digits(n, base)
    return prod(ds) + sum(ds)


def product_plus_sum_bound(base: int) -> int:
    if base < 2:
        raise ValueError("base must be at least 2")
    width = 1
    while True:
        image_max = (base - 1) ** width + width * (base - 1)
        if image_max < base ** (width - 1):
            return image_max
        width += 1


def _canonical_cycle(values: list[int]) -> tuple[int, ...]:
    least = min(range(len(values)), key=values.__getitem__)
    return tuple(values[least:] + values[:least])


def _cycles_below(bound: int, step: Callable[[int], int]) -> tuple[tuple[int, ...], ...]:
    settled: set[int] = set()
    found: set[tuple[int, ...]] = set()
    for start in range(bound + 1):
        if start in settled:
            continue
        path: list[int] = []
        positions: dict[int, int] = {}
        n = start
        while n not in positions and n not in settled:
            positions[n] = len(path)
            path.append(n)
            n = step(n)
        if n in positions:
            found.add(_canonical_cycle(path[positions[n] :]))
        settled.update(path)
    return tuple(sorted(found))


def cycles(base: int) -> tuple[tuple[int, ...], ...]:
    bound = product_plus_sum_bound(base)
    return _cycles_below(bound, lambda n: product_plus_sum_step(n, base))
