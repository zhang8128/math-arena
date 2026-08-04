#!/usr/bin/env python3
"""Independent exact verifier for T19 tame and wild records."""

from __future__ import annotations

import json
import sys
from math import isqrt
from pathlib import Path


def is_prime_trial(n: int) -> bool:
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    for divisor in range(3, isqrt(n) + 1, 2):
        if n % divisor == 0:
            return False
    return True


def factor_trial(n: int) -> dict[int, int]:
    factors: dict[int, int] = {}
    divisor = 2
    while divisor * divisor <= n:
        while n % divisor == 0:
            factors[divisor] = factors.get(divisor, 0) + 1
            n //= divisor
        divisor = 3 if divisor == 2 else divisor + 2
    if n > 1:
        factors[n] = factors.get(n, 0) + 1
    return factors


def divisors_of_product(n: int, x: int) -> list[int]:
    factors = factor_trial(x)
    factors[n] = factors.get(n, 0) + 1
    values = [1]
    for prime, exponent in factors.items():
        powers = [prime**power for power in range(exponent + 1)]
        values = [value * power for value in values for power in powers]
    return sorted(values)


def exact_identity(n: int, x: int, y: int, z: int) -> bool:
    return min(n, x, y, z) > 0 and 4 * x * y * z == n * (x * y + x * z + y * z)


def independent_tame_solution(n: int) -> tuple[int, int, int] | None:
    m = (n - 1) // 24
    for k in range(1, 12 * m + 1):
        x = 6 * m + k
        q = n * x
        for y in divisors_of_product(n, x):
            if y < x:
                continue
            numerator = 4 * x * y - n * (x + y)
            if numerator <= 0:
                continue
            denominator = n * x * y
            if denominator % numerator:
                continue
            z = denominator // numerator
            if y <= z and q % z == 0 and exact_identity(n, x, y, z):
                return x, y, z
    return None


def check_120t_plus_73_identity(count: int) -> None:
    for t in range(count):
        n = 120 * t + 73
        x = 30 * t + 20
        y = (6 * t + 4) * n
        z = (15 * t + 10) * n
        q = n * x
        if q % y or q % z or not exact_identity(n, x, y, z):
            raise SystemExit(f"FAIL n=120*{t}+73 identity")


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {Path(sys.argv[0]).name} RESULTS.json")
    payload = json.loads(Path(sys.argv[1]).read_text())
    m_range = payload["m_range"]
    primes = [int(n) for n in payload["prime_n"]]
    solutions = payload["solutions"]
    wild = [int(n) for n in payload["wild"]]
    if len(primes) != len(solutions) + len(wild):
        raise SystemExit("FAIL prime partition does not match solutions plus wild")

    for n in primes:
        if not is_prime_trial(n) or n % 24 != 1:
            raise SystemExit(f"FAIL n={n} is not a prime congruent to 1 mod 24")
    for raw_n, raw_solution in solutions.items():
        n = int(raw_n)
        x = int(raw_solution["x"])
        y = int(raw_solution["y"])
        z = int(raw_solution["z"])
        q = n * x
        if not x <= y <= z:
            raise SystemExit(f"FAIL n={n} denominators are unordered")
        if q % y or q % z:
            raise SystemExit(f"FAIL n={n} stored solution is not tame")
        if not exact_identity(n, x, y, z):
            raise SystemExit(f"FAIL n={n} stored solution is not exact")
    for n in wild:
        found = independent_tame_solution(n)
        if found is not None:
            raise SystemExit(f"FAIL n={n} recorded wild but verifier found {found}")

    identity_checks = 1_000
    check_120t_plus_73_identity(identity_checks)

    print(
        f"PASS range={m_range[0]}..{m_range[1]} primes={len(primes)} "
        f"triples={len(solutions)} wild={len(wild)} "
        f"identity_checks={identity_checks}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
