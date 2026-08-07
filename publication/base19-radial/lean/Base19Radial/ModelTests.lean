import Base19Radial.Model

namespace Base19Radial

def tinyProblem : Problem := {
  base := 3
  kinds := [.digit, .digit, .carry]
  leading := [0]
  equations := [{
    left := .var 0
    right := .var 1
    target := .lit 0
    carryIn := none
    carryOut := some 2
    provenance := "tiny"
  }]
}

example : tinyProblem.Satisfies [1, 2, 1] := by decide

example : ¬ tinyProblem.Satisfies [0, 0, 0] := by decide

end Base19Radial
