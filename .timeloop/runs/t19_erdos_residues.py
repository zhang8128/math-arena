#!/usr/bin/env python3
"""Explore tame Erdős–Straus solutions for primes n = 24m + 1."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from sympy import factorint, isprime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from erdos_straus import first_tame_solution


def _empty_state(modulus: int) -> dict[str, object]:
    return {
        "m_range": [1, 0],
        "last_m": 0,
        "modulus": modulus,
        "prime_n": [],
        "solutions": {},
        "wild": [],
        "residue_summary": {},
    }


def _load_state(resume: Path | None, modulus: int) -> dict[str, object]:
    if resume is None:
        return _empty_state(modulus)
    state = json.loads(resume.read_text())
    if state.get("modulus") != modulus:
        raise ValueError("resume modulus does not match requested modulus")
    return state


def _summarize(state: dict[str, object]) -> None:
    modulus = int(state["modulus"])
    solutions = state["solutions"]
    wild = state["wild"]
    if not isinstance(solutions, dict) or not isinstance(wild, list):
        raise TypeError("invalid state")
    summary: dict[str, dict[str, int]] = {}
    for raw_n in [*solutions.keys(), *wild]:
        n = int(raw_n)
        residue = str(((n - 1) // 24) % modulus)
        bucket = summary.setdefault(residue, {"solved": 0, "total": 0})
        bucket["total"] += 1
        if str(n) in solutions:
            bucket["solved"] += 1
    state["residue_summary"] = dict(sorted(summary.items(), key=lambda item: int(item[0])))


def _write_atomic(path: Path, state: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(state, sort_keys=True) + "\n")
    os.replace(temporary, path)


def explore(
    max_m: int,
    modulus: int,
    checkpoint: Path,
    resume: Path | None,
    checkpoint_every: int = 25,
) -> dict[str, object]:
    if max_m < 1:
        raise ValueError("max_m must be positive")
    if modulus < 1:
        raise ValueError("modulus must be positive")
    if checkpoint_every < 1:
        raise ValueError("checkpoint_every must be positive")
    state = _load_state(resume, modulus)
    last_m = int(state.get("last_m", 0))
    prime_n = state["prime_n"]
    solutions = state["solutions"]
    wild = state["wild"]
    if not isinstance(prime_n, list) or not isinstance(solutions, dict) or not isinstance(wild, list):
        raise TypeError("invalid state")

    for m in range(last_m + 1, max_m + 1):
        n = 24 * m + 1
        if isprime(n):
            prime_n.append(n)
            selected: dict[str, int] | None = None
            for k in range(1, 12 * m + 1):
                x = 6 * m + k
                q_factors = {int(prime): int(exponent) for prime, exponent in factorint(x).items()}
                q_factors[n] = q_factors.get(n, 0) + 1
                pair = first_tame_solution(n, x, q_factors)
                if pair is not None:
                    y, z = pair
                    selected = {"m": m, "k": k, "x": x, "y": y, "z": z}
                    break
            if selected is None:
                wild.append(n)
            else:
                solutions[str(n)] = selected
        state["last_m"] = m
        state["m_range"] = [1, m]
        if m % checkpoint_every == 0:
            _summarize(state)
            _write_atomic(checkpoint, state)

    _summarize(state)
    _write_atomic(checkpoint, state)
    return state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-m", type=int, required=True)
    parser.add_argument("--modulus", type=int, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--checkpoint-every", type=int, default=25)
    args = parser.parse_args()
    result = explore(
        args.max_m,
        args.modulus,
        args.checkpoint,
        args.resume,
        args.checkpoint_every,
    )
    json.dump(result, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
