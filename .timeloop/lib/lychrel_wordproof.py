"""Exact certificates for reverse-add families with homogeneous growing blocks."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations


DigitWord = tuple[int, ...]
Polynomial = tuple[int, ...]


def _trim(polynomial: Polynomial) -> Polynomial:
    end = len(polynomial)
    while end > 1 and polynomial[end - 1] == 0:
        end -= 1
    return polynomial[:end] if end else (0,)


def _add(left: Polynomial, right: Polynomial) -> Polynomial:
    size = max(len(left), len(right))
    return _trim(
        tuple(
            (left[index] if index < len(left) else 0)
            + (right[index] if index < len(right) else 0)
            for index in range(size)
        )
    )


def _scale(polynomial: Polynomial, factor: int) -> Polynomial:
    return _trim(tuple(coefficient * factor for coefficient in polynomial))


def _multiply_by_q(polynomial: Polynomial) -> Polynomial:
    if polynomial == (0,):
        return polynomial
    return (0,) + polynomial


@dataclass(frozen=True)
class ParametricWord:
    """Fixed digit fragments separated by repeat blocks of length ``n``."""

    base: int
    fragments: tuple[DigitWord, ...]
    repeats: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.base < 2:
            raise ValueError("base must be at least 2")
        if len(self.fragments) != len(self.repeats) + 1:
            raise ValueError("fragments must have exactly one more item than repeats")
        if not self.fragments:
            raise ValueError("at least one fragment is required")
        for fragment in self.fragments:
            for digit in fragment:
                if digit < 0 or digit >= self.base:
                    raise ValueError("fragment digit is outside the base")
        for digit in self.repeats:
            if digit not in (0, self.base - 1):
                raise ValueError("repeat digits must be 0 or base-1")

    def render(self, n: int) -> DigitWord:
        if n < 0:
            raise ValueError("n must be nonnegative")
        result = list(self.fragments[0])
        for repeat, fragment in zip(self.repeats, self.fragments[1:]):
            result.extend((repeat,) * n)
            result.extend(fragment)
        return tuple(result)


@dataclass(frozen=True)
class RecurrenceHit:
    start: int
    period: int
    certificate: tuple[ParametricWord, ...]


def digits_value(digits: DigitWord, base: int) -> int:
    if base < 2:
        raise ValueError("base must be at least 2")
    value = 0
    for digit in digits:
        if digit < 0 or digit >= base:
            raise ValueError("digit is outside the base")
        value = value * base + digit
    return value


def evaluate_polynomial(polynomial: Polynomial, q: int) -> int:
    value = 0
    for coefficient in reversed(polynomial):
        value = value * q + coefficient
    return value


def value_polynomial(word: ParametricWord) -> Polynomial:
    """Compile a word's numeric value as a polynomial in ``q = base**n``."""
    polynomial: Polynomial = (0,)
    for index, fragment in enumerate(word.fragments):
        polynomial = _add(
            _scale(polynomial, word.base ** len(fragment)),
            (digits_value(fragment, word.base),),
        )
        if index < len(word.repeats):
            polynomial = _multiply_by_q(polynomial)
            if word.repeats[index] == word.base - 1:
                polynomial = _add(polynomial, (-1, 1))
    return _trim(polynomial)


def reversed_word(word: ParametricWord) -> ParametricWord:
    return ParametricWord(
        word.base,
        tuple(tuple(reversed(fragment)) for fragment in reversed(word.fragments)),
        tuple(reversed(word.repeats)),
    )


def shift_parameter(polynomial: Polynomial, base: int) -> Polynomial:
    """Substitute ``q -> base*q``, corresponding to ``n -> n+1``."""
    return _trim(
        tuple(
            coefficient * (base**degree)
            for degree, coefficient in enumerate(polynomial)
        )
    )


def reverse_add_digits(digits: DigitWord, base: int) -> DigitWord:
    if not digits:
        raise ValueError("a number must contain at least one digit")
    output = []
    carry = 0
    for index in range(len(digits)):
        total = digits[len(digits) - 1 - index] + digits[index] + carry
        output.append(total % base)
        carry = total // base
    if carry:
        output.append(carry)
    return tuple(reversed(output))


def _is_canonical(word: ParametricWord) -> bool:
    # The first digit is stable for all n >= 1, so n=0 and n=1 cover every
    # possible leading-token regime (repeat blocks disappear only at n=0).
    for n in (0, 1):
        rendered = word.render(n)
        if not rendered or (len(rendered) > 1 and rendered[0] == 0):
            return False
    return True


def verify_cycle(words: tuple[ParametricWord, ...]) -> bool:
    if not words:
        return False
    base = words[0].base
    if any(word.base != base or not _is_canonical(word) for word in words):
        return False
    for index, word in enumerate(words):
        actual = _add(value_polynomial(word), value_polynomial(reversed_word(word)))
        if index + 1 < len(words):
            expected = value_polynomial(words[index + 1])
        else:
            expected = shift_parameter(value_polynomial(words[0]), base)
        if actual != expected:
            return False
    return True


def _reverse_add_polynomial(word: ParametricWord) -> Polynomial:
    return _add(value_polynomial(word), value_polynomial(reversed_word(word)))


def fixed_palindrome_mismatch(word: ParametricWord) -> tuple[int, int, int] | None:
    """Return an outer fixed-digit mismatch valid for every parameter value."""
    left = word.fragments[0]
    right = word.fragments[-1]
    for offset in range(min(len(left), len(right))):
        left_digit = left[offset]
        right_digit = right[len(right) - 1 - offset]
        if left_digit != right_digit:
            return offset, left_digit, right_digit
    return None


def infer_words(
    base: int,
    small: DigitWord,
    large: DigitWord,
    *,
    max_blocks: int = 4,
) -> tuple[ParametricWord, ...]:
    """Enumerate templates satisfying exactly ``W(0)=small, W(1)=large``."""
    if base < 2:
        raise ValueError("base must be at least 2")
    if max_blocks < 1:
        raise ValueError("max_blocks must be positive")
    difference = len(large) - len(small)
    if difference < 1 or difference > max_blocks:
        return ()
    allowed = {0, base - 1}
    deletion_candidates = [
        index for index, digit in enumerate(large) if digit in allowed
    ]
    inferred = set()
    for deleted in combinations(deletion_candidates, difference):
        deleted_set = set(deleted)
        if tuple(
            digit for index, digit in enumerate(large) if index not in deleted_set
        ) != small:
            continue
        fragments = []
        start = 0
        for index in deleted:
            fragments.append(large[start:index])
            start = index + 1
        fragments.append(large[start:])
        inferred.add(
            ParametricWord(
                base,
                tuple(fragments),
                tuple(large[index] for index in deleted),
            )
        )
    return tuple(
        sorted(inferred, key=lambda word: (word.repeats, word.fragments))
    )


def infer_cycle(
    base: int,
    first: tuple[DigitWord, ...],
    second: tuple[DigitWord, ...],
    *,
    max_blocks: int = 4,
) -> tuple[ParametricWord, ...] | None:
    """Infer one cycle, accepting it only through exact polynomial identities."""
    if not first or len(first) != len(second):
        return None
    candidate_sets = [
        infer_words(base, small, large, max_blocks=max_blocks)
        for small, large in zip(first, second)
    ]
    if any(not candidates for candidates in candidate_sets):
        return None
    paths = [(candidate,) for candidate in candidate_sets[0]]
    for candidates in candidate_sets[1:]:
        next_paths = []
        expected_polynomials = {
            candidate: value_polynomial(candidate) for candidate in candidates
        }
        for path in paths:
            actual = _reverse_add_polynomial(path[-1])
            for candidate in candidates:
                if actual == expected_polynomials[candidate]:
                    next_paths.append(path + (candidate,))
        paths = next_paths
        if not paths:
            return None
    for path in paths:
        if _reverse_add_polynomial(path[-1]) == shift_parameter(
            value_polynomial(path[0]), base
        ):
            return path
    return None


def _can_delete_allowed(base: int, small: DigitWord, large: DigitWord) -> bool:
    difference = len(large) - len(small)
    if difference < 0:
        return False
    allowed = {0, base - 1}

    @lru_cache(maxsize=None)
    def visit(small_index: int, large_index: int, deleted: int) -> bool:
        if deleted > difference:
            return False
        if large_index == len(large):
            return small_index == len(small) and deleted == difference
        if small_index < len(small) and small[small_index] == large[large_index]:
            if visit(small_index + 1, large_index + 1, deleted):
                return True
        return (
            large[large_index] in allowed
            and visit(small_index, large_index + 1, deleted + 1)
        )

    return visit(0, 0, 0)


def scan_recurrences(
    base: int,
    orbit: tuple[DigitWord, ...],
    *,
    periods: range,
    max_blocks: int = 4,
) -> tuple[RecurrenceHit, ...]:
    """Return the earliest, then shortest exact cycle in one bounded orbit."""
    ordered_periods = tuple(sorted(set(periods)))
    for start in range(len(orbit)):
        for period in ordered_periods:
            if period < 1:
                continue
            if start + 2 * period > len(orbit):
                continue
            first = orbit[start : start + period]
            second = orbit[start + period : start + 2 * period]
            increases = {
                len(large) - len(small) for small, large in zip(first, second)
            }
            if len(increases) != 1:
                continue
            increase = next(iter(increases))
            if increase < 1 or increase > max_blocks:
                continue
            if any(
                not _can_delete_allowed(base, small, large)
                for small, large in zip(first, second)
            ):
                continue
            certificate = infer_cycle(
                base,
                first,
                second,
                max_blocks=max_blocks,
            )
            if certificate is None:
                continue
            if any(fixed_palindrome_mismatch(word) is None for word in certificate):
                continue
            return (RecurrenceHit(start, period, certificate),)
    return ()
