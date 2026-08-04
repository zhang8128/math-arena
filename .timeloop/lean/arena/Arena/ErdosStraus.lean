import Mathlib

/-! # Checked Erdős–Straus identities

Exact positive-control families and one residue family recovered by T19.
-/

theorem erdosStraus_even (k : ℕ) (hk : 0 < k) :
    (4 : ℚ) / (2 * k) = 1 / k + 1 / (2 * k) + 1 / (2 * k) := by
  field_simp [Nat.ne_of_gt hk]
  ring

theorem erdosStraus_three_mod_four (k : ℕ) :
    (4 : ℚ) / (4 * k + 3) =
      1 / (k + 1) +
      1 / (((4 * k + 3) * (k + 1)) * 2) +
      1 / (((4 * k + 3) * (k + 1)) * 2) := by
  field_simp
  ring

theorem erdosStraus_120t_plus_73 (t : ℕ) :
    (4 : ℚ) / (120 * t + 73) =
      1 / (30 * t + 20) +
      1 / ((6 * t + 4) * (120 * t + 73)) +
      1 / ((15 * t + 10) * (120 * t + 73)) := by
  field_simp
  ring

#print axioms erdosStraus_even
#print axioms erdosStraus_three_mod_four
#print axioms erdosStraus_120t_plus_73
