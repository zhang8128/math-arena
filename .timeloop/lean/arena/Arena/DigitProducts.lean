import Arena.Basic

/-! # Digit-product-plus-sum map

Machine-checked modular consequences of the fixed-point equation.
-/

open Nat List

theorem digitProductPlusSum_modEq (base n : ℕ) (hb : 2 ≤ base) :
    (base.digits n).prod + (base.digits n).sum ≡
      (base.digits n).prod + n [MOD base - 1] := by
  rcases eq_or_lt_of_le hb with h2 | h3
  · subst h2
    exact Nat.modEq_one
  · obtain ⟨k, hk, rfl⟩ : ∃ k, 2 ≤ k ∧ base = k + 1 :=
      ⟨base - 1, by omega, by omega⟩
    simp only [Nat.add_sub_cancel]
    have hbm : (k + 1) % k = 1 := by
      rw [Nat.add_mod_left, Nat.mod_eq_of_lt (by omega)]
    have hsum : ((k + 1).digits n).sum ≡ n [MOD k] :=
      (Nat.modEq_digits_sum k (k + 1) hbm n).symm
    exact Nat.ModEq.add Nat.ModEq.rfl hsum

theorem digitProductPlusSum_fixed_product_zero (base n : ℕ) (hb : 2 ≤ base)
    (hfix : (base.digits n).prod + (base.digits n).sum = n) :
    (base.digits n).prod ≡ 0 [MOD base - 1] := by
  have h := digitProductPlusSum_modEq base n hb
  rw [hfix] at h
  apply Nat.ModEq.add_right_cancel' n
  simpa using h.symm

#print axioms digitProductPlusSum_modEq
#print axioms digitProductPlusSum_fixed_product_zero
