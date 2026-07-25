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

/-! ## T5's mechanism, in general form

The `decide` proofs above settle single moduli. This is the theorem they were
instances of: for **any** base and **any** modulus `m` with `x^d ≡ x (mod m)`,
the digit-power map is congruent to the identity mod `gcd(b-1, m)`.

Measured empirically on 2026-07-25 across four exponents and eight congruence
classes. Proved here.
-/


/-- Elementwise congruence lifts to sums under `map`. -/
theorem sum_map_pow_modEq (d m : ℕ) (hm : ∀ x : ℕ, x ^ d ≡ x [MOD m]) :
    ∀ l : List ℕ, (l.map (· ^ d)).sum ≡ l.sum [MOD m]
  | [] => Nat.ModEq.refl 0
  | (x :: xs) => by
      simp only [List.map_cons, List.sum_cons]
      exact Nat.ModEq.add (hm x) (sum_map_pow_modEq d m hm xs)

/-- **T5's mechanism, in general form.** -/
theorem digitPow_modEq (base d m : ℕ) (hb : 2 ≤ base)
    (hm : ∀ x : ℕ, x ^ d ≡ x [MOD m]) (n : ℕ) :
    ((base.digits n).map (· ^ d)).sum ≡ n [MOD Nat.gcd (base - 1) m] := by
  rcases eq_or_lt_of_le hb with h2 | h3
  · subst h2
    simp only [show (2:ℕ) - 1 = 1 from rfl, Nat.gcd_one_left]
    exact Nat.modEq_one
  · obtain ⟨k, hk, rfl⟩ : ∃ k, 2 ≤ k ∧ base = k + 1 := ⟨base - 1, by omega, by omega⟩
    simp only [Nat.add_sub_cancel]
    have hbm : (k + 1) % k = 1 := by
      rw [Nat.add_mod_left, Nat.mod_eq_of_lt (by omega)]
    have h1 : n ≡ ((k + 1).digits n).sum [MOD k] :=
      Nat.modEq_digits_sum k (k + 1) hbm n
    exact ((sum_map_pow_modEq d m hm _).of_dvd (Nat.gcd_dvd_right _ _)).trans
          ((h1.of_dvd (Nat.gcd_dvd_left _ _)).symm)

-- Audit: confirm the proof rests on no `sorry`.
#print axioms digitPow_modEq
