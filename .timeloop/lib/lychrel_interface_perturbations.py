"""Exact single-boundary perturbations of parametric digit words."""

from __future__ import annotations

from dataclasses import dataclass

from lychrel_wordproof import ParametricWord


@dataclass(frozen=True, order=True)
class InterfaceMove:
    phase: int
    interface: int
    shift: int


def move_interface(
    words: tuple[ParametricWord, ...],
    move: InterfaceMove,
) -> tuple[ParametricWord, ...]:
    """Move one repeat boundary while preserving flattened fixed digits."""
    if not words:
        raise ValueError("at least one phase is required")
    if move.phase < 0 or move.phase >= len(words):
        raise ValueError("phase is outside the cycle")
    if move.shift == 0 or abs(move.shift) > 2:
        raise ValueError("shift must be one or two columns")

    word = words[move.phase]
    if move.interface < 0 or move.interface >= len(word.repeats):
        raise ValueError("interface is outside the phase")
    if len(word.fragments) != len(word.repeats) + 1:
        raise ValueError("phase has inconsistent fragments and repeats")

    fragments = list(word.fragments)
    left = fragments[move.interface]
    right = fragments[move.interface + 1]
    if move.shift > 0:
        if len(right) <= move.shift:
            raise ValueError("move would empty the right fragment")
        left = left + right[: move.shift]
        right = right[move.shift :]
    else:
        amount = -move.shift
        if len(left) <= amount:
            raise ValueError("move would empty the left fragment")
        left, right = left[:-amount], left[-amount:] + right
    fragments[move.interface] = left
    fragments[move.interface + 1] = right

    changed = ParametricWord(word.base, tuple(fragments), word.repeats)
    return words[: move.phase] + (changed,) + words[move.phase + 1 :]


def all_moves(
    words: tuple[ParametricWord, ...],
    *,
    max_shift: int = 2,
) -> tuple[InterfaceMove, ...]:
    """Enumerate every admissible nonzero move up to ``max_shift``."""
    if type(max_shift) is not int or max_shift < 1 or max_shift > 2:
        raise ValueError("max_shift must be one or two")
    moves = []
    for phase, word in enumerate(words):
        for interface in range(len(word.repeats)):
            for shift in range(-max_shift, max_shift + 1):
                if shift == 0:
                    continue
                move = InterfaceMove(phase, interface, shift)
                try:
                    move_interface(words, move)
                except ValueError:
                    continue
                moves.append(move)
    return tuple(moves)


def n_zero_relevant_moves(
    words: tuple[ParametricWord, ...],
    *,
    max_shift: int = 2,
) -> tuple[InterfaceMove, ...]:
    """Return moves visible in the wrap output at the ``n=0`` filter."""
    return tuple(
        move for move in all_moves(words, max_shift=max_shift) if move.phase == 0
    )
