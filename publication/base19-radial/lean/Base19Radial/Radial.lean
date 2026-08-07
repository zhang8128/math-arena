import Base19Radial.Model

namespace Base19Radial

abbrev State := List Int

def restrict (assignment : Assignment) (variables : List Nat) : State :=
  variables.map fun id => assignment[id]?.getD 0

def Compatible (assignment : Assignment) (variables : List Nat) (state : State) : Prop :=
  restrict assignment variables = state

inductive LocalKind where
  | digit
  | carry
  | leading
deriving Repr, DecidableEq

def State.validFor (base : Int) : List LocalKind → State → Bool
  | [], [] => true
  | .digit :: kinds, value :: values =>
      decide (0 ≤ value ∧ value < base) && validFor base kinds values
  | .carry :: kinds, value :: values =>
      (value == 0 || value == 1) && validFor base kinds values
  | .leading :: kinds, value :: values =>
      decide (0 < value ∧ value < base) && validFor base kinds values
  | _, _ => false

inductive LocalAtom where
  | input (index : Nat)
  | output (index : Nat)
  | hidden (index : Nat)
  | lit (value : Int)
deriving Repr, DecidableEq

def LocalAtom.eval (atom : LocalAtom) (input output hidden : State) : Int :=
  match atom with
  | .input index => input[index]?.getD 0
  | .output index => output[index]?.getD 0
  | .hidden index => hidden[index]?.getD 0
  | .lit value => value

structure LocalColumn where
  left : LocalAtom
  right : LocalAtom
  target : LocalAtom
  carryIn : LocalAtom
  carryOut : LocalAtom
  provenance : String
deriving Repr, DecidableEq

def LocalColumn.check
    (column : LocalColumn) (base : Int) (input output hidden : State) : Bool :=
  decide (
    column.left.eval input output hidden +
      column.right.eval input output hidden +
      column.carryIn.eval input output hidden =
    column.target.eval input output hidden +
      base * column.carryOut.eval input output hidden)

structure Layer where
  inputVariables : List Nat
  outputVariables : List Nat
  hiddenVariables : List Nat
  inputKinds : List LocalKind
  outputKinds : List LocalKind
  hiddenKinds : List LocalKind
  equations : List LocalColumn
deriving Repr, DecidableEq

def Layer.Step (problem : Problem) (layer : Layer) (input output : State) : Prop :=
  ∃ hidden,
    input.validFor problem.base layer.inputKinds = true ∧
      output.validFor problem.base layer.outputKinds = true ∧
      hidden.validFor problem.base layer.hiddenKinds = true ∧
      layer.equations.all
        (fun column => column.check problem.base input output hidden) = true

def Layer.LocallySatisfied
    (problem : Problem) (layer : Layer) (assignment : Assignment) : Prop :=
  layer.Step problem
    (restrict assignment layer.inputVariables)
    (restrict assignment layer.outputVariables)

def layersCover (problem : Problem) (layers : List Layer) : Prop :=
  ∀ assignment, problem.Satisfies assignment →
    ∀ layer, layer ∈ layers → layer.LocallySatisfied problem assignment

namespace Frontier

abbrev Set := State → Prop

def empty : Set := fun _ => False

def ofList (states : List State) : Set := fun state => state ∈ states

def Closed
    (problem : Problem) (layer : Layer) (current next : Set) : Prop :=
  ∀ input, current input →
    ∀ output, Layer.Step problem layer input output → next output

def ClosedChainFrom (problem : Problem) :
    List Nat → List Layer → List Set → Prop
  | _, [], [_] => True
  | previousVariables, layer :: layers, current :: next :: rest =>
      layer.inputVariables = previousVariables ∧
        Closed problem layer current next ∧
        ClosedChainFrom problem layer.outputVariables layers (next :: rest)
  | _, _, _ => False

def ClosedChain (problem : Problem) (layers : List Layer)
    (frontiers : List Set) : Prop :=
  ClosedChainFrom problem [] layers frontiers

end Frontier

private theorem contradiction_of_closed_chain
    (problem : Problem) (assignment : Assignment)
    (satisfies : problem.Satisfies assignment) :
    ∀ (previousVariables : List Nat) (layers : List Layer)
      (frontiers : List Frontier.Set),
      layersCover problem layers →
      Frontier.ClosedChainFrom problem previousVariables layers frontiers →
      (frontiers.headD Frontier.empty) (restrict assignment previousVariables) →
      frontiers.getLast? = some Frontier.empty →
      False := by
  intro previousVariables layers
  induction layers generalizing previousVariables with
  | nil =>
      intro frontiers _hcover hclosed hinit hempty
      cases frontiers with
      | nil => simp [Frontier.ClosedChainFrom] at hclosed
      | cons current rest =>
          cases rest with
          | nil =>
              simp at hempty
              subst current
              simp [Frontier.empty] at hinit
          | cons next rest => simp [Frontier.ClosedChainFrom] at hclosed
  | cons layer layers induction =>
      intro frontiers hcover hclosed hinit hempty
      cases frontiers with
      | nil => simp [Frontier.ClosedChainFrom] at hclosed
      | cons current rest =>
          cases rest with
          | nil => simp [Frontier.ClosedChainFrom] at hclosed
          | cons next rest =>
              rcases hclosed with ⟨haligned, hclosedHead, hclosedTail⟩
              have hlocal : layer.LocallySatisfied problem assignment :=
                hcover assignment satisfies layer (by simp)
              have hstep : Layer.Step problem layer
                  (restrict assignment layer.inputVariables)
                  (restrict assignment layer.outputVariables) :=
                hlocal
              have hnext : next (restrict assignment layer.outputVariables) :=
                hclosedHead (restrict assignment layer.inputVariables)
                  (by simpa [haligned] using hinit)
                  (restrict assignment layer.outputVariables) hstep
              have hcoverTail : layersCover problem layers := by
                intro tailAssignment tailSatisfies tailLayer tailMem
                exact hcover tailAssignment tailSatisfies tailLayer (by simp [tailMem])
              apply induction layer.outputVariables (next :: rest) hcoverTail hclosedTail
              · exact hnext
              · simpa using hempty

theorem unsat_of_closed_empty_frontier
    (problem : Problem) (layers : List Layer) (frontiers : List Frontier.Set)
    (_shape : frontiers.length = layers.length + 1)
    (hcover : layersCover problem layers)
    (hinit : (frontiers.headD Frontier.empty) [])
    (hclosed : Frontier.ClosedChain problem layers frontiers)
    (hempty : frontiers.getLast? = some Frontier.empty) :
    ¬ ∃ assignment, problem.Satisfies assignment := by
  rintro ⟨assignment, satisfies⟩
  apply contradiction_of_closed_chain problem assignment satisfies [] layers frontiers
    hcover hclosed
  · simpa [restrict] using hinit
  · exact hempty

end Base19Radial
