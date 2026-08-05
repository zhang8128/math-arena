#!/usr/bin/env python3
"""Calibrate and search exact multi-interface reverse-add certificates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from lychrel_wordproof import (  # noqa: E402
    ParametricWord,
    digits_value,
    evaluate_polynomial,
    fixed_palindrome_mismatch,
    infer_cycle,
    reverse_add_digits,
    reversed_word,
    scan_recurrences,
    shift_parameter,
    value_polynomial,
    verify_cycle,
)


BASE17_ALPHABET = "0123456789abcdefg"
BASE17_LEFT = "10023ab83e3b983cfgec556g4g010"
BASE17_MIDDLE = "0fgcg10fg505gf020cgf"
BASE17_RIGHT = "gg11g4f655ddggb299b3d38bb320g"


def parse_digits(value: str, alphabet: str) -> tuple[int, ...]:
    return tuple(alphabet.index(character.lower()) for character in value)


def add_polynomials(
    left: tuple[int, ...], right: tuple[int, ...]
) -> tuple[int, ...]:
    size = max(len(left), len(right))
    result = tuple(
        (left[index] if index < len(left) else 0)
        + (right[index] if index < len(right) else 0)
        for index in range(size)
    )
    end = len(result)
    while end > 1 and result[end - 1] == 0:
        end -= 1
    return result[:end]


def base17_start(n: int) -> tuple[int, ...]:
    return parse_digits(
        BASE17_LEFT + "0" * n + BASE17_MIDDLE + "g" * n + BASE17_RIGHT,
        BASE17_ALPHABET,
    )


def orbit(start: tuple[int, ...], base: int, steps: int) -> tuple[tuple[int, ...], ...]:
    values = [start]
    for _ in range(steps - 1):
        values.append(reverse_add_digits(values[-1], base))
    return tuple(values)


def int_to_digits(value: int, base: int) -> tuple[int, ...]:
    if value < 0:
        raise ValueError("value must be nonnegative")
    if value == 0:
        return (0,)
    result = []
    while value:
        value, digit = divmod(value, base)
        result.append(digit)
    return tuple(reversed(result))


def is_palindrome(value: tuple[int, ...]) -> bool:
    return value == tuple(reversed(value))


def first_bounded_survivor(
    base: int,
    *,
    max_seed: int,
    steps: int,
) -> tuple[int, tuple[tuple[int, ...], ...]] | None:
    for seed in range(1, max_seed + 1):
        values = [int_to_digits(seed, base)]
        if is_palindrome(values[0]):
            continue
        for _ in range(steps):
            values.append(reverse_add_digits(values[-1], base))
            if is_palindrome(values[-1]):
                break
        else:
            return seed, tuple(values)
    return None


def serialize_word(word: ParametricWord) -> dict[str, object]:
    polynomial = value_polynomial(word)
    reverse_polynomial = value_polynomial(reversed_word(word))
    return {
        "fragments": [list(fragment) for fragment in word.fragments],
        "repeats": list(word.repeats),
        "value_polynomial": list(polynomial),
        "reverse_polynomial": list(reverse_polynomial),
        "sum_polynomial": list(add_polynomials(polynomial, reverse_polynomial)),
        "palindrome_mismatch": list(fixed_palindrome_mismatch(word) or ()),
    }


def calibrate_base17() -> dict[str, object]:
    full_orbit = orbit(base17_start(2), 17, 12)
    first_cycle = full_orbit[:6]
    second_cycle = full_orbit[6:12]
    if second_cycle[0] != base17_start(3):
        raise AssertionError("published base-17 cycle did not increment n")
    certificate = infer_cycle(17, first_cycle, second_cycle, max_blocks=2)
    if certificate is None or not verify_cycle(certificate):
        raise AssertionError("failed to infer the published base-17 certificate")
    mismatches = tuple(fixed_palindrome_mismatch(word) for word in certificate)
    if any(mismatch is None for mismatch in mismatches):
        raise AssertionError("a phase lacks a uniform non-palindrome witness")

    numeric_checks = 0
    for n in range(9):
        for phase, word in enumerate(certificate):
            rendered = word.render(n)
            actual = digits_value(rendered, 17) + digits_value(
                tuple(reversed(rendered)), 17
            )
            successor = certificate[(phase + 1) % len(certificate)]
            expected = digits_value(
                successor.render(n + (phase == len(certificate) - 1)), 17
            )
            if actual != expected:
                raise AssertionError("independent integer replay disagrees")
            numeric_checks += 1

    phases = [serialize_word(word) for word in certificate]
    for phase, evidence in enumerate(phases):
        expected = value_polynomial(certificate[(phase + 1) % len(certificate)])
        if phase == len(certificate) - 1:
            expected = shift_parameter(expected, 17)
        if tuple(evidence["sum_polynomial"]) != expected:
            raise AssertionError("serialized coefficient identity disagrees")
        for n in range(4):
            if evaluate_polynomial(value_polynomial(certificate[phase]), 17**n) != digits_value(
                certificate[phase].render(n), 17
            ):
                raise AssertionError("polynomial evaluation disagrees")

    return {
        "kind": "published_control",
        "base": 17,
        "source_parameter_start": 2,
        "period": 6,
        "interfaces": 2,
        "verified": True,
        "proof": "coefficient equality in q=17^n plus fixed outer-digit mismatches",
        "independent_integer_checks": numeric_checks,
        "phases": phases,
    }


def scan_bases(
    *,
    min_base: int,
    max_base: int,
    steps: int,
    max_period: int,
    max_blocks: int,
    max_seed: int,
) -> dict[str, object]:
    results = []
    for base in range(min_base, max_base + 1):
        survivor = first_bounded_survivor(
            base,
            max_seed=max_seed,
            steps=steps,
        )
        if survivor is None:
            results.append(
                {
                    "base": base,
                    "max_seed": max_seed,
                    "survivor": None,
                    "hits": [],
                }
            )
            continue
        seed, values = survivor
        hits = scan_recurrences(
            base,
            values,
            periods=range(2, max_period + 1),
            max_blocks=max_blocks,
        )
        serialized_hits = []
        for hit in hits:
            serialized_hits.append(
                {
                    "start": hit.start,
                    "period": hit.period,
                    "verified": verify_cycle(hit.certificate),
                    "phases": [serialize_word(word) for word in hit.certificate],
                }
            )
        results.append(
            {
                "base": base,
                "seed_decimal": seed,
                "seed_digits": list(int_to_digits(seed, base)),
                "survival_steps": steps,
                "final_digits": len(values[-1]),
                "hits": serialized_hits,
            }
        )
    return {
        "kind": "bounded_multi_interface_scan",
        "bounds": {
            "min_base": min_base,
            "max_base": max_base,
            "max_seed": max_seed,
            "steps": steps,
            "periods": [2, max_period],
            "max_blocks": max_blocks,
        },
        "positive_control": calibrate_base17(),
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibrate-base17", action="store_true")
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--min-base", type=int, default=3)
    parser.add_argument("--max-base", type=int, default=40)
    parser.add_argument("--max-seed", type=int, default=5000)
    parser.add_argument("--steps", type=int, default=1200)
    parser.add_argument("--max-period", type=int, default=12)
    parser.add_argument("--max-blocks", type=int, default=4)
    args = parser.parse_args()
    if args.scan:
        payload = scan_bases(
            min_base=args.min_base,
            max_base=args.max_base,
            max_seed=args.max_seed,
            steps=args.steps,
            max_period=args.max_period,
            max_blocks=args.max_blocks,
        )
    elif args.calibrate_base17:
        payload = calibrate_base17()
    else:
        parser.error("select --calibrate-base17 or --scan")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
