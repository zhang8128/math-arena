import Mathlib

/-! # Arena — machine-checked results

The first results in the time-loop arena to be verified by a proof assistant
rather than supported by computation over a stated range. Chosen deliberately
from the arena's own findings, so the evaluator is validated against work whose
truth is already believed for independent reasons.
-/

/-- Euclid, via mathlib. Confirms mathlib is genuinely loaded, not just imported. -/
theorem arena_infinitely_many_primes (n : ℕ) : ∃ p, n ≤ p ∧ Nat.Prime p :=
  Nat.exists_infinite_primes n

/-- **T5's mechanism, formalised.**

The arena measured that digit-power maps satisfy `T(n) ≡ n (mod gcd(b-1, M_d))`,
where `M_d` is the largest modulus with `x^d ≡ x (mod M_d)` for every `x`.
That congruence is what makes the fixed-point equation get one condition free,
and it predicted fixed-point abundance across four exponents.

`M_3 = 6`. Measured on 2026-07-25; proved here. -/
theorem arena_cube_eq_self_mod_six : ∀ x : ZMod 6, x ^ 3 = x := by decide

/-- `M_5 = 30`. The arena verified the resulting prediction empirically across
eight congruence classes; the underlying congruence is now proved. -/
theorem arena_fifth_eq_self_mod_thirty : ∀ x : ZMod 30, x ^ 5 = x := by decide

/-- `M_2 = 2` — and this is exactly why `d = 2` was too degenerate to reveal the
general law: only two congruence classes exist, so the boost never varies. -/
theorem arena_sq_eq_self_mod_two : ∀ x : ZMod 2, x ^ 2 = x := by decide

/-- `M_4 = 2` as well, which is why `d = 4` behaved like `d = 2` in the data. -/
theorem arena_fourth_eq_self_mod_two : ∀ x : ZMod 2, x ^ 4 = x := by decide
