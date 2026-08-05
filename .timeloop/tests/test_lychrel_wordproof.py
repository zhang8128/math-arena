from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from lychrel_wordproof import (
    ParametricWord,
    digits_value,
    evaluate_polynomial,
    fixed_palindrome_mismatch,
    infer_cycle,
    infer_words,
    reverse_add_digits,
    reversed_word,
    scan_recurrences,
    value_polynomial,
    verify_cycle,
)


def word(base: int, fragments: tuple[str, ...], repeats: str) -> ParametricWord:
    return ParametricWord(
        base,
        tuple(tuple(int(character) for character in fragment) for fragment in fragments),
        tuple(int(character) for character in repeats),
    )


def published_binary_cycle() -> tuple[ParametricWord, ...]:
    return (
        word(2, ("10", "1101", "00"), "10"),
        word(2, ("11", "1000", "01"), "01"),
        word(2, ("10", "11010", "00"), "10"),
        word(2, ("11", "00101", "01"), "01"),
    )


def parse_digits(value: str, alphabet: str) -> tuple[int, ...]:
    return tuple(alphabet.index(character.lower()) for character in value)


def base17_sample_cycles(n: int = 2) -> tuple[
    tuple[tuple[int, ...], ...], tuple[tuple[int, ...], ...]
]:
    alphabet = "0123456789abcdefg"
    outer_left = "10023ab83e3b983cfgec556g4g010"
    middle = "0fgcg10fg505gf020cgf"
    outer_right = "gg11g4f655ddggb299b3d38bb320g"
    start = parse_digits(
        outer_left + "0" * n + middle + "g" * n + outer_right,
        alphabet,
    )
    expected_next = parse_digits(
        outer_left + "0" * (n + 1) + middle + "g" * (n + 1) + outer_right,
        alphabet,
    )
    orbit = [start]
    for _ in range(11):
        orbit.append(reverse_add_digits(orbit[-1], 17))
    assert orbit[6] == expected_next
    return tuple(orbit[:6]), tuple(orbit[6:12])


def test_two_interface_word_compiles_to_exact_values() -> None:
    candidate = ParametricWord(5, ((1,), (2,), (3,)), (0, 4))
    polynomial = value_polynomial(candidate)
    for n in range(5):
        assert evaluate_polynomial(polynomial, 5**n) == digits_value(
            candidate.render(n), 5
        )


def test_reversing_tokens_matches_reversing_every_rendered_word() -> None:
    candidate = ParametricWord(7, ((1, 2), (3,), (4, 5)), (0, 6))
    reverse = reversed_word(candidate)
    for n in range(4):
        assert reverse.render(n) == tuple(reversed(candidate.render(n)))


def test_published_binary_cycle_verifies_with_parameter_shift_on_wrap() -> None:
    cycle = published_binary_cycle()
    assert verify_cycle(cycle)
    for n in range(4):
        for index, candidate in enumerate(cycle):
            expected = cycle[(index + 1) % len(cycle)].render(
                n + (index == len(cycle) - 1)
            )
            assert reverse_add_digits(candidate.render(n), 2) == expected


def test_verifier_rejects_noncanonical_zero_padded_words() -> None:
    padded = []
    for candidate in published_binary_cycle():
        fragments = list(candidate.fragments)
        fragments[0] = (0,) + fragments[0]
        fragments[-1] = fragments[-1] + (0,)
        padded.append(
            ParametricWord(candidate.base, tuple(fragments), candidate.repeats)
        )
    assert not verify_cycle(tuple(padded))


def test_fixed_outer_mismatch_proves_non_palindromicity_for_all_parameters() -> None:
    candidate = ParametricWord(5, ((1, 2), (3,), (4, 4)), (0, 4))
    assert fixed_palindrome_mismatch(candidate) == (0, 1, 4)
    for n in range(5):
        rendered = candidate.render(n)
        assert rendered != tuple(reversed(rendered))


def test_inference_enumerates_ambiguous_repeat_boundaries() -> None:
    small = (1, 0, 2, 4, 3)
    large = (1, 0, 0, 2, 4, 4, 3)
    candidates = infer_words(5, small, large, max_blocks=4)
    assert candidates
    assert all(candidate.render(0) == small for candidate in candidates)
    assert all(candidate.render(1) == large for candidate in candidates)
    assert any(candidate.repeats == (0, 4) for candidate in candidates)


def test_inference_rejects_non_homogeneous_insertions() -> None:
    assert infer_words(5, (1, 2, 3), (1, 2, 2, 3), max_blocks=2) == ()


def test_cycle_inference_is_filtered_by_exact_polynomial_identities() -> None:
    expected = published_binary_cycle()
    first = tuple(candidate.render(0) for candidate in expected)
    second = tuple(candidate.render(1) for candidate in expected)
    inferred = infer_cycle(2, first, second, max_blocks=2)
    assert inferred is not None
    assert verify_cycle(inferred)
    assert tuple(candidate.render(0) for candidate in inferred) == first
    assert tuple(candidate.render(1) for candidate in inferred) == second


def test_base17_published_family_is_inferred_and_certified() -> None:
    first_cycle, second_cycle = base17_sample_cycles(n=2)
    certificate = infer_cycle(17, first_cycle, second_cycle, max_blocks=2)
    assert certificate is not None
    assert verify_cycle(certificate)
    assert all(fixed_palindrome_mismatch(word) is not None for word in certificate)
    assert tuple(word.render(0) for word in certificate) == first_cycle
    assert tuple(word.render(1) for word in certificate) == second_cycle


def test_scanner_detects_base17_control_at_period_six() -> None:
    first_cycle, second_cycle = base17_sample_cycles(n=2)
    values = first_cycle + second_cycle + (
        reverse_add_digits(second_cycle[-1], 17),
    )
    hits = scan_recurrences(
        17,
        values,
        periods=range(2, 13),
        max_blocks=4,
    )
    assert [(hit.start, hit.period) for hit in hits] == [(0, 6)]
    assert verify_cycle(hits[0].certificate)
