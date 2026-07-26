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

open Nat List in
/-! ## The alternating analogue — mod (b+1) instead of (b-1)

Found by asking what the T5 proof *rested on*: `b ≡ 1 (mod b-1)`. The same
argument with `b ≡ -1 (mod b+1)` gives an alternating version. Predicted from
structure, confirmed computationally, proved below.
-/


/-- Elementwise congruence lifts to ALTERNATING sums. Stated over `List ℤ` so the
cons-recursion matches without coercion getting in the way. -/
theorem alternatingSum_map_pow_zmodEq (d m : ℕ) (hm : ∀ x : ℤ, x ^ d ≡ x [ZMOD m]) :
    ∀ l : List ℤ, (l.map (fun z => z ^ d)).alternatingSum ≡ l.alternatingSum [ZMOD m]
  | [] => by simp
  | (x :: xs) => by
      simp only [List.map_cons, List.alternatingSum_cons]
      exact Int.ModEq.sub (hm x) (alternatingSum_map_pow_zmodEq d m hm xs)

/-- **The alternating analogue of T5's mechanism.**

`b ≡ -1 (mod b+1)`, so `bⁱ ≡ (-1)ⁱ` and `n` is congruent to the ALTERNATING digit
sum mod `b+1` — "casting out elevens". Combined with `x^d ≡ x (mod m)`, the
alternating digit-power map is congruent to the identity mod `gcd(b+1, m)`,
exactly mirroring `gcd(b-1, m)` for plain sums.

Predicted from the structure of the T5 proof, confirmed computationally with zero
counterexamples over `b ≤ 12`, `d ≤ 5`, `n < 20000`, then proved here. -/
theorem altDigitPow_zmodEq (base d m : ℕ) (hm : ∀ x : ℤ, x ^ d ≡ x [ZMOD m]) (n : ℕ) :
    (((base.digits n).map (fun x : ℕ => (x : ℤ))).map (fun z => z ^ d)).alternatingSum
      ≡ (n : ℤ) [ZMOD (Nat.gcd (base + 1) m : ℕ)] := by
  have hb1 : ((base : ℤ)) ≡ (-1 : ℤ) [ZMOD ((base + 1 : ℕ) : ℤ)] :=
    Int.modEq_iff_dvd.mpr ⟨-1, by push_cast; ring⟩
  have key := Nat.zmodeq_ofDigits_digits (base + 1) base (-1 : ℤ) hb1 n
  rw [Nat.ofDigits_neg_one] at key
  have h1 := key.of_dvd (Int.natCast_dvd_natCast.2 (Nat.gcd_dvd_left (base + 1) m))
  have h2 := (alternatingSum_map_pow_zmodEq d m hm
    ((base.digits n).map (fun x : ℕ => (x : ℤ)))).of_dvd
    (Int.natCast_dvd_natCast.2 (Nat.gcd_dvd_right (base + 1) m))
  exact h2.trans h1.symm

-- Audit: neither proof rests on a `sorry`.
#print axioms digitPow_modEq
#print axioms altDigitPow_zmodEq
