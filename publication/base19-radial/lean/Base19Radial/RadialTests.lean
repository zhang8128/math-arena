import Base19Radial.Radial

namespace Base19Radial

def radialTinyImpossibleProblemColumn : Column := {
  left := .lit 1
  right := .lit 1
  target := .lit 0
  carryIn := none
  carryOut := none
  provenance := "tiny-impossible"
}

def radialTinyImpossibleColumn : LocalColumn := {
  left := .lit 1
  right := .lit 1
  target := .lit 0
  carryIn := .lit 0
  carryOut := .lit 0
  provenance := "tiny-impossible"
}

def radialTinyProblem : Problem := {
  base := 2
  kinds := []
  leading := []
  equations := [radialTinyImpossibleProblemColumn]
}

def radialTinyPassLayer : Layer := {
  inputVariables := []
  outputVariables := []
  hiddenVariables := []
  inputKinds := []
  outputKinds := []
  hiddenKinds := []
  equations := []
}

def radialTinyFailLayer : Layer := {
  inputVariables := []
  outputVariables := []
  hiddenVariables := []
  inputKinds := []
  outputKinds := []
  hiddenKinds := []
  equations := [radialTinyImpossibleColumn]
}

def radialTinyLayers : List Layer := [radialTinyPassLayer, radialTinyFailLayer]

def radialTinyInitialFrontier : Frontier.Set := fun state => state = []

def radialTinyMiddleFrontier : Frontier.Set := fun state => state = []

def radialTinyFrontiers : List Frontier.Set :=
  [radialTinyInitialFrontier, radialTinyMiddleFrontier, Frontier.empty]

theorem radialTinyProblemUnsat :
    ¬ ∃ assignment, radialTinyProblem.Satisfies assignment := by
  apply unsat_of_closed_empty_frontier
    radialTinyProblem radialTinyLayers radialTinyFrontiers
  · rfl
  · intro assignment satisfies layer layer_mem
    have : layer = radialTinyPassLayer ∨ layer = radialTinyFailLayer := by
      simpa [radialTinyLayers] using layer_mem
    rcases this with rfl | rfl
    · change Layer.Step radialTinyProblem radialTinyPassLayer [] []
      exact ⟨[], rfl, rfl, rfl, rfl⟩
    · have hcheck :
          radialTinyImpossibleProblemColumn.check 2 assignment = true := by
        simpa [radialTinyProblem] using satisfies.2.2
      have hfalse :
          radialTinyImpossibleProblemColumn.check 2 assignment = false := by rfl
      rw [hfalse] at hcheck
      contradiction
  · rfl
  · refine ⟨rfl, ?_, ?_⟩
    · intro input input_mem output step
      rcases step with ⟨hidden, _, outputValid, hiddenValid, _⟩
      cases output with
      | nil => rfl
      | cons value values =>
          simp [State.validFor, radialTinyPassLayer] at outputValid
    · refine ⟨rfl, ?_, ?_⟩
      · intro input input_mem output step
        rcases step with ⟨hidden, inputValid, outputValid, hiddenValid, equations⟩
        simp [radialTinyProblem, radialTinyFailLayer, radialTinyImpossibleColumn,
          LocalColumn.check, LocalAtom.eval] at equations
      · trivial
  · rfl

#print axioms radialTinyProblemUnsat

end Base19Radial
