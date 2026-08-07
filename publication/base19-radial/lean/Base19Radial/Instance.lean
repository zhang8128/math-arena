import Base19Radial.Model
import Base19Radial.Generated.InstanceData

namespace Base19Radial

structure PhaseShape where
  fragmentLengths : List Nat
  repeats : List Nat
deriving Repr, DecidableEq

def base19Topology : List PhaseShape := [
  { fragmentLengths := [26, 25, 31], repeats := [0, 16] },
  { fragmentLengths := [29, 23, 31], repeats := [16, 0] },
  { fragmentLengths := [29, 23, 31], repeats := [0, 16] },
  { fragmentLengths := [29, 23, 31], repeats := [0, 16] },
  { fragmentLengths := [29, 23, 31], repeats := [0, 16] },
  { fragmentLengths := [29, 23, 31], repeats := [0, 16] }
]

inductive NamedAtom where
  | variable (name : String)
  | literal (value : Int)
deriving Repr, DecidableEq

structure NamedColumn where
  phase : Nat
  column : Nat
  left : NamedAtom
  right : NamedAtom
  target : NamedAtom
  carryIn : Option String
  carryOut : Option String
  provenance : String
deriving Repr, DecidableEq

private def phaseShape (phase : Nat) : PhaseShape :=
  base19Topology[phase]?.getD { fragmentLengths := [], repeats := [] }

private def fixedAtoms (phase fragment length : Nat) : List NamedAtom :=
  (List.range length).map fun offset =>
    .variable s!"p{phase}:f{fragment}:d{offset}"

def renderPhase (phase n : Nat) : List NamedAtom :=
  let shape := phaseShape phase
  (List.range shape.fragmentLengths.length).flatMap fun fragment =>
    let repeated :=
      if fragment = 0 then []
      else
        let referenceDigit := shape.repeats[fragment - 1]?.getD 0
        let targetDigit : Int := if referenceDigit = 16 then 18 else 0
        List.replicate n (.literal targetDigit)
    let length := shape.fragmentLengths[fragment]?.getD 0
    repeated ++ fixedAtoms phase fragment length

private def atomAt (atoms : List NamedAtom) (index : Nat) : NamedAtom :=
  atoms[index]?.getD (.literal 0)

private def phaseColumns (phase : Nat) : List NamedColumn :=
  let source := renderPhase phase 0
  let nextPhase := (phase + 1) % 6
  let outputN := if phase = 5 then 1 else 0
  let output := renderPhase nextPhase outputN
  (List.range output.length).map fun column => {
    phase := phase
    column := column
    left := atomAt source column
    right := atomAt source.reverse column
    target := atomAt output.reverse column
    carryIn := if column = 0 then none else some s!"c:p{phase}:n0:col{column - 1}"
    carryOut :=
      if column + 1 = output.length then none
      else some s!"c:p{phase}:n0:col{column}"
    provenance := s!"phase={phase},n=0,column={column}"
  }

def allColumns : List NamedColumn :=
  (List.range 6).flatMap phaseColumns

private def inInterval (value lower upper : Nat) : Bool :=
  decide (lower ≤ value ∧ value ≤ upper)

def selectedCoordinate (phase column : Nat) : Bool :=
  let inBands :=
    match phase with
    | 0 => inInterval column 0 33 || inInterval column 48 82
    | 1 | 2 | 3 | 4 => inInterval column 0 33 || inInterval column 49 82
    | 5 => inInterval column 0 33 || inInterval column 49 83
    | _ => false
  inBands && !(phase = 5 && column = 82)

def candidateNamedColumns : List NamedColumn :=
  allColumns.filter fun equation =>
    selectedCoordinate equation.phase equation.column

def candidateProvenances : List String :=
  candidateNamedColumns.map (·.provenance)

def variableNames : List String := generatedVariableNames

def candidate : Problem := generatedCandidate

end Base19Radial
