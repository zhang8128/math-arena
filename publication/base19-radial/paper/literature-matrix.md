# Literature matrix

This matrix records the support used for historical and methodological
sentences in `main.tex`.  It is a claim audit, not a novelty search result.

| Claim | Status | Primary source | Supporting location | Citation key |
| --- | --- | --- | --- | --- |
| Computer-aided proofs should identify the role of computation and make supporting code and data available as transparent, surveyable material. | supported | London Mathematical Society, “Computer Aided Proofs” | paragraphs 1–3; page says “Updated November 2024” | `lmsComputerAidedProofs` |
| Lean 4 is both an extensible theorem prover and an efficient functional programming language. | supported | de Moura and Ullrich, *The Lean 4 Theorem Prover and Programming Language* | abstract and system-description introduction | `deMouraUllrich2021` |
| Bounded-width constraint structure can make CSP solution linear in the number of variables with exponential dependence on width. | supported | Freuder, *Complexity of K-Tree Structured Constraint Satisfaction Problems* | abstract; complexity statement | `Freuder1990` |
| Tree clustering reorganizes a constraint network into an acyclic structure supporting backtrack-free processing. | supported | Dechter and Pearl, *Tree Clustering for Constraint Networks* | abstract | `DechterPearl1989` |
| DRAT-trim checks and trims expressive clausal proofs. | supported | Wetzler, Heule, and Hunt, *DRAT-trim: Efficient Checking and Trimming Using Expressive Clausal Proofs* | abstract and Section 1 | `WetzlerHeuleHunt2014` |
| LRAT adds hints to DRAT so that a simple checker can be implemented in a trusted theorem-prover environment. | supported | Cruz-Filipe et al., *Efficient Certified RAT Verification* | abstract | `CruzFilipeEtAl2017` |
| FRAT is a solver-to-elaborator format designed to reduce the cost of elaboration to LRAT. | supported | Baek, Carneiro, and Heule, *A Flexible Proof Format for SAT Solver-Elaborator Communication* | abstract | `BaekCarneiroHeule2022` |
| CaDiCaL distinguishes unknown, satisfiable, and unsatisfiable solver returns, and failed assumptions need not form a minimal core. | supported | CaDiCaL public API header | `Solver::solve`, return codes 0/10/20; `Solver::failed` comment | `cadical301` |
| Z3 integer arithmetic uses mathematical integers, and its LIA engine uses cuts and branch-and-bound techniques. | supported | Z3 Guide, “Arithmetic” | “Basics” and “Algorithmic Fragments of Arithmetic” | `z3Arithmetic` |
| OEIS A060382 defines the least start of a conjecturally palindrome-free reverse-and-add sequence in each base; the entry says only its base-2 term is proved. | supported as historical context, not used as proof | OEIS A060382 | definition and first comment | `oeisA060382` |
| David Seal reported a period-six, self-similar base-17 reverse-and-add construction in January 1996. | supported as historical provenance | K. S. Brown's transcription of Seal's report | opening paragraph and “Base 17, Period 6” table | `brownSeal` |
| Novelty | not established | Targeted checks covered the sources above and searches for the exact finite topology/frontier formulation. Search absence is not evidence of novelty. | The manuscript therefore claims only a new artifact result, not priority or literature-wide novelty. | none |

## Scope decisions

- The Seal page and OEIS entry motivate the fixed topology but do not prove any
  equation in the artifact.
- CSP-width references explain why a small live interface is useful; the
  concrete frontier is still checked directly.
- DRAT, LRAT, FRAT, and CaDiCaL describe a possible stronger proof-trace
  endpoint.  No such trace is claimed here.
- The related-work search found no source that establishes the exact frozen
  base-19 system in this artifact.  That observation is deliberately not
  promoted to a novelty claim.
