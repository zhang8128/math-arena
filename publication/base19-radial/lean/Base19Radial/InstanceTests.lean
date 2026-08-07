import Base19Radial.Instance

namespace Base19Radial

example : candidate.equations.length = 409 := by decide

example : candidate.kinds.count .digit = 409 := by decide

example : candidate.kinds.count .carry = 410 := by decide

example : candidate.equations.head?.map (·.provenance) =
    some "phase=0,n=0,column=0" := by decide

example : candidate.equations.getLast?.map (·.provenance) =
    some "phase=5,n=0,column=83" := by decide

example : candidate.Valid := by decide

end Base19Radial
