import Base19Radial.Instance

open Base19Radial

private def jsonString (value : String) : String :=
  "\"" ++ value ++ "\""

private def jsonOptionalString (value : Option String) : String :=
  match value with
  | none => "null"
  | some item => jsonString item

private def jsonAtom (atom : NamedAtom) : String :=
  match atom with
  | .variable name => "{\"variable\":" ++ jsonString name ++ "}"
  | .literal value => "{\"literal\":" ++ toString value ++ "}"

private def jsonEquation (equation : NamedColumn) : String :=
  "{\"carry_in\":" ++ jsonOptionalString equation.carryIn ++
  ",\"carry_out\":" ++ jsonOptionalString equation.carryOut ++
  ",\"left\":" ++ jsonAtom equation.left ++
  ",\"provenance\":" ++ jsonString equation.provenance ++
  ",\"right\":" ++ jsonAtom equation.right ++
  ",\"target\":" ++ jsonAtom equation.target ++ "}"

private def manifestJson : String :=
  "{\"base\":19," ++
  "\"content_sha256\":\"ff79f31cbc55d7c463e6a14faedaad58d880509d5769e56b9a4bd06ebacd9040\"," ++
  "\"equation_count\":409," ++
  "\"equations\":[" ++
  String.intercalate "," (candidateNamedColumns.map jsonEquation) ++
  "],\"schema\":\"base19-radial-equations-v1\"," ++
  "\"topology_sha256\":\"a0d84abc99ecd225fd80dbe6ce4ece1e230f39f89353a48695f1b85401b693c6\"}\n"

def main : IO Unit :=
  IO.print manifestJson
