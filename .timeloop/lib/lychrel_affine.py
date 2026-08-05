"""Exact bivariate certificates for affine lifts of reverse-add words."""

from __future__ import annotations

from dataclasses import dataclass


BasePolynomial = tuple[int, ...]
BivariatePolynomial = tuple[BasePolynomial, ...]


def _trim_base(polynomial: BasePolynomial) -> BasePolynomial:
    end = len(polynomial)
    while end > 1 and polynomial[end - 1] == 0:
        end -= 1
    return polynomial[:end] if end else (0,)


def _add_base(left: BasePolynomial, right: BasePolynomial) -> BasePolynomial:
    size = max(len(left), len(right))
    return _trim_base(
        tuple(
            (left[index] if index < len(left) else 0)
            + (right[index] if index < len(right) else 0)
            for index in range(size)
        )
    )


def _multiply_by_base_power(
    polynomial: BasePolynomial, power: int
) -> BasePolynomial:
    if power < 0:
        raise ValueError("power must be nonnegative")
    if polynomial == (0,):
        return polynomial
    return (0,) * power + polynomial


def _trim_q(polynomial: BivariatePolynomial) -> BivariatePolynomial:
    end = len(polynomial)
    while end > 1 and polynomial[end - 1] == (0,):
        end -= 1
    return polynomial[:end] if end else ((0,),)


def _add_bivariate(
    left: BivariatePolynomial, right: BivariatePolynomial
) -> BivariatePolynomial:
    size = max(len(left), len(right))
    return _trim_q(
        tuple(
            _add_base(
                left[index] if index < len(left) else (0,),
                right[index] if index < len(right) else (0,),
            )
            for index in range(size)
        )
    )


def _multiply_by_q(polynomial: BivariatePolynomial) -> BivariatePolynomial:
    if polynomial == ((0,),):
        return polynomial
    return ((0,),) + polynomial


def _evaluate_base(polynomial: BasePolynomial, base: int) -> int:
    value = 0
    for coefficient in reversed(polynomial):
        value = value * base + coefficient
    return value


@dataclass(frozen=True)
class AffineDigit:
    """A digit ``d + slope*(base-reference_base)`` with slope zero or one."""

    intercept: int
    slope: int
    reference_base: int = 17

    def __post_init__(self) -> None:
        if self.reference_base < 2:
            raise ValueError("reference_base must be at least 2")
        if self.intercept < 0 or self.intercept >= self.reference_base:
            raise ValueError("intercept must be a digit at the reference base")
        if self.slope not in (0, 1):
            raise ValueError("slope must be zero or one")

    def evaluate(self, base: int) -> int:
        if base < self.reference_base:
            raise ValueError("base must be at least the reference base")
        value = self.intercept + self.slope * (base - self.reference_base)
        if value < 0 or value >= base:
            raise ValueError("affine value is not a digit in this base")
        return value

    def polynomial(self) -> BasePolynomial:
        return _trim_base(
            (self.intercept - self.reference_base * self.slope, self.slope)
        )


@dataclass(frozen=True)
class AffineWord:
    """Fixed affine fragments separated by repeat blocks ``0^n`` or ``(b-1)^n``."""

    fragments: tuple[tuple[AffineDigit, ...], ...]
    repeats: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.fragments) != len(self.repeats) + 1:
            raise ValueError("fragments must have exactly one more item than repeats")
        if not any(self.fragments):
            raise ValueError("at least one fixed digit is required")
        if any(repeat not in (0, 1) for repeat in self.repeats):
            raise ValueError("repeat kind must be zero or one")
        bases = {
            digit.reference_base
            for fragment in self.fragments
            for digit in fragment
        }
        if len(bases) != 1:
            raise ValueError("all affine digits must share a reference base")

    @property
    def reference_base(self) -> int:
        return next(
            digit.reference_base
            for fragment in self.fragments
            for digit in fragment
        )

    def render(self, base: int, n: int) -> tuple[int, ...]:
        if n < 0:
            raise ValueError("n must be nonnegative")
        result = [digit.evaluate(base) for digit in self.fragments[0]]
        for repeat, fragment in zip(self.repeats, self.fragments[1:]):
            result.extend(((base - 1) if repeat else 0,) * n)
            result.extend(digit.evaluate(base) for digit in fragment)
        return tuple(result)


def _fragment_polynomial(fragment: tuple[AffineDigit, ...]) -> BasePolynomial:
    polynomial: BasePolynomial = (0,)
    for digit in fragment:
        polynomial = _add_base(
            _multiply_by_base_power(polynomial, 1),
            digit.polynomial(),
        )
    return polynomial


def value_bivariate(word: AffineWord) -> BivariatePolynomial:
    """Compile a word in ``Z[b,q]``, with ``q=b^n``."""
    polynomial: BivariatePolynomial = ((0,),)
    for index, fragment in enumerate(word.fragments):
        polynomial = tuple(
            _multiply_by_base_power(coefficient, len(fragment))
            for coefficient in polynomial
        )
        polynomial = _add_bivariate(
            polynomial,
            (_fragment_polynomial(fragment),),
        )
        if index < len(word.repeats):
            polynomial = _multiply_by_q(polynomial)
            if word.repeats[index] == 1:
                polynomial = _add_bivariate(
                    polynomial,
                    ((-1,), (1,)),
                )
    return _trim_q(polynomial)


def evaluate_bivariate(
    polynomial: BivariatePolynomial, base: int, q: int
) -> int:
    value = 0
    for coefficient in reversed(polynomial):
        value = value * q + _evaluate_base(coefficient, base)
    return value


def reverse_affine_word(word: AffineWord) -> AffineWord:
    return AffineWord(
        tuple(tuple(reversed(fragment)) for fragment in reversed(word.fragments)),
        tuple(reversed(word.repeats)),
    )


def shift_q_parameter(polynomial: BivariatePolynomial) -> BivariatePolynomial:
    """Substitute ``q -> b*q``."""
    return _trim_q(
        tuple(
            _multiply_by_base_power(coefficient, degree)
            for degree, coefficient in enumerate(polynomial)
        )
    )


def _is_canonical(word: AffineWord) -> bool:
    for n in (0, 1):
        rendered = word.render(word.reference_base, n)
        if not rendered or (len(rendered) > 1 and rendered[0] == 0):
            return False
    return True


def verify_affine_cycle(words: tuple[AffineWord, ...]) -> bool:
    if not words:
        return False
    reference_base = words[0].reference_base
    if any(
        word.reference_base != reference_base or not _is_canonical(word)
        for word in words
    ):
        return False
    for index, word in enumerate(words):
        actual = _add_bivariate(
            value_bivariate(word),
            value_bivariate(reverse_affine_word(word)),
        )
        expected = value_bivariate(words[(index + 1) % len(words)])
        if index == len(words) - 1:
            expected = shift_q_parameter(expected)
        if actual != expected:
            return False
    return True
