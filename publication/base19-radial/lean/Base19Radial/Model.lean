namespace Base19Radial

inductive VarKind where
  | digit
  | carry
deriving Repr, DecidableEq

inductive Atom where
  | var (id : Nat)
  | lit (value : Int)
deriving Repr, DecidableEq

structure Column where
  left : Atom
  right : Atom
  target : Atom
  carryIn : Option Nat
  carryOut : Option Nat
  provenance : String
deriving Repr, DecidableEq

abbrev Assignment := List Int

structure Problem where
  base : Int
  kinds : List VarKind
  leading : List Nat
  equations : List Column
deriving Repr, DecidableEq

def Atom.eval (atom : Atom) (assignment : Assignment) : Option Int :=
  match atom with
  | .var id => assignment[id]?
  | .lit value => some value

def Atom.validDigit (atom : Atom) (problem : Problem) : Bool :=
  match atom with
  | .var id => problem.kinds[id]? == some .digit
  | .lit value => decide (0 ≤ value ∧ value < problem.base)

def Column.validFor (column : Column) (problem : Problem) : Bool :=
  let carryValid (id : Option Nat) : Bool :=
    match id with
    | none => true
    | some index => problem.kinds[index]? == some .carry
  column.left.validDigit problem &&
    column.right.validDigit problem &&
    column.target.validDigit problem &&
    carryValid column.carryIn &&
    carryValid column.carryOut

def Problem.valid (problem : Problem) : Bool :=
  decide (2 ≤ problem.base) &&
    problem.leading.all (fun id => problem.kinds[id]? == some .digit) &&
    problem.equations.all (fun column => column.validFor problem)

def Problem.Valid (problem : Problem) : Prop :=
  problem.valid = true

instance (problem : Problem) : Decidable problem.Valid := by
  unfold Problem.Valid
  infer_instance

private def carryValue (assignment : Assignment) (id : Option Nat) : Option Int :=
  match id with
  | none => some 0
  | some index => assignment[index]?

private def Column.values (column : Column) (assignment : Assignment) :
    Option (Int × Int × Int × Int × Int) := do
  let left ← column.left.eval assignment
  let right ← column.right.eval assignment
  let target ← column.target.eval assignment
  let carryIn ← carryValue assignment column.carryIn
  let carryOut ← carryValue assignment column.carryOut
  pure (left, right, target, carryIn, carryOut)

def Column.Holds (column : Column) (base : Int) (assignment : Assignment) : Prop :=
  match column.values assignment with
  | some (left, right, target, carryIn, carryOut) =>
      left + right + carryIn = target + base * carryOut
  | none => False

def Column.check (column : Column) (base : Int) (assignment : Assignment) : Bool :=
  match column.values assignment with
  | some (left, right, target, carryIn, carryOut) =>
      decide (left + right + carryIn = target + base * carryOut)
  | none => false

theorem Column.check_eq_true_iff
    (column : Column) (base : Int) (assignment : Assignment) :
    column.check base assignment = true ↔ column.Holds base assignment := by
  unfold Column.check Column.Holds
  split <;> simp_all

def Problem.assignmentValid (problem : Problem) (assignment : Assignment) : Bool :=
  assignment.length == problem.kinds.length &&
    (List.range problem.kinds.length).all (fun id =>
      match problem.kinds[id]?, assignment[id]? with
      | some .digit, some value => decide (0 ≤ value ∧ value < problem.base)
      | some .carry, some value => value == 0 || value == 1
      | _, _ => false) &&
    problem.leading.all (fun id =>
      match assignment[id]? with
      | some value => decide (0 < value)
      | none => false)

def Problem.Satisfies (problem : Problem) (assignment : Assignment) : Prop :=
  problem.Valid ∧
    problem.assignmentValid assignment = true ∧
    problem.equations.all (fun column => column.check problem.base assignment) = true

instance (problem : Problem) (assignment : Assignment) :
    Decidable (problem.Satisfies assignment) := by
  unfold Problem.Satisfies
  infer_instance

end Base19Radial
