# Citation matrix

This audit was performed on 8 August 2026. The prior bibliography and
literature matrix were used only to locate candidates; every supported row
below was checked against the linked publisher record, official project source,
official database entry, or identified transcription.

| Claim | Status | Primary source | Supporting location | Citation key |
| --- | --- | --- | --- | --- |
| Computer-aided proofs should state where and how computation is used, publish the supporting code and files, and make the code transparent and surveyable. | supported | [London Mathematical Society, “Computer Aided Proofs”](https://www.lms.ac.uk/publications/policies/computeraidedproofs) | Policy paragraphs 1--3; page marked “Updated November 2024” | `lmsComputerAidedProofs` |
| Lean 4 is an extensible interactive theorem prover and an efficient functional programming language. | supported | [de Moura and Ullrich, *The Lean 4 Theorem Prover and Programming Language*](https://doi.org/10.1007/978-3-030-79876-5_37) | Abstract and Section 1, especially the extensibility and programming-language descriptions; publisher record pp. 625--635 | `deMouraUllrich2021` |
| A fixed bound on k-tree width makes the CSP running time linear in the number of variables, with exponential dependence on width. | supported | [Freuder, *Complexity of K-Tree Structured Constraint Satisfaction Problems*](https://cdn.aaai.org/AAAI/1990/AAAI90-001.pdf) | Abstract and Section 1; the central bound is stated as \(O(nd^{k+1})\); AAAI-90 pp. 4--9 | `Freuder1990` |
| Tree clustering regroups constraints into an acyclic structure that supports backtrack-free processing. | supported | [Dechter and Pearl, *Tree Clustering for Constraint Networks*](https://doi.org/10.1016/0004-3702(89)90037-4) | Publisher abstract; *Artificial Intelligence* 38(3), pp. 353--366 | `DechterPearl1989` |
| DRAT-trim checks DRAT proofs and can emit trimmed formulas and optimized proofs. | supported | [Wetzler, Heule, and Hunt, *DRAT-trim: Efficient Checking and Trimming Using Expressive Clausal Proofs*](https://doi.org/10.1007/978-3-319-09284-3_31) | Publisher abstract; SAT 2014, pp. 422--429 | `WetzlerHeuleHunt2014` |
| LRAT extends DRAT with hints that enable a simple, fast validator suitable for implementation in a trusted theorem-prover environment. | supported | [Cruz-Filipe et al., *Efficient Certified RAT Verification*](https://doi.org/10.1007/978-3-319-63046-5_14) | Publisher abstract; CADE 26, pp. 220--236 | `CruzFilipeEtAl2017` |
| FRAT lets a SAT solver provide extra information to reduce the cost of later elaboration to LRAT. | supported | [Baek, Carneiro, and Heule, *A Flexible Proof Format for SAT Solver-Elaborator Communication*](https://doi.org/10.46298/lmcs-18(2:3)2022) | Abstract of the version of record; LMCS 18(2), pp. 3:1--3:21 | `BaekCarneiroHeule2022` |
| CaDiCaL distinguishes unknown, satisfiable, and unsatisfiable solver returns, and a failed-assumption core need not be minimal. | supported | [CaDiCaL 3.0.1 public API header](https://github.com/arminbiere/cadical/blob/rel-3.0.1/src/cadical.hpp) and [official release](https://github.com/arminbiere/cadical/releases/tag/rel-3.0.1) | `Solver::solve` comment at header lines 292--306 gives return codes 0/10/20; `Solver::failed` comment at lines 363--370 says the core need not be minimal; release is tag `rel-3.0.1`, commit `c607304` | `cadical301` |
| Z3 integer and real sorts denote mathematical values rather than machine integers or floating-point values; its LIA engine uses cuts and branch-and-bound techniques. | supported | [Official Z3 Guide, “Arithmetic”](https://microsoft.github.io/z3guide/docs/theories/Arithmetic/) | “Basics” and “Algorithmic Fragments of Arithmetic” | `z3Arithmetic` |
| OEIS A060382 records, for each base, the least start of a conjecturally palindrome-free reverse-and-add sequence; the entry says only its base-2 term is proved. | supported as historical context, not as proof of this artifact | [OEIS A060382](https://oeis.org/A060382) | Definition and first comment (“Only a(2) is proved”); entry author and status fields | `oeisA060382` |
| David Seal reported in January 1996 a period-six, self-similar base-17 reverse-and-add construction. | supported as historical provenance | [K. S. Brown’s transcription of Seal’s report](https://www.mathpages.com/home/dseal.htm) | Opening two lines and “Base 17, Period 6” table, especially iterations 0 and 6 | `brownSeal` |
| At the frozen Lean 4.32.2 commit, `bv_decide` bitblasts a reflected bit-vector expression, obtains an LRAT certificate, checks it, and constructs a proof whose soundness reduces to the verified checker. | supported | [Lean 4 commit `f3b06c705e6c85f5314019d5d3baab0fec5b580c`](https://github.com/leanprover/lean4/commit/f3b06c705e6c85f5314019d5d3baab0fec5b580c) | [`Std/Tactic/BVDecide/Reflect.lean`](https://github.com/leanprover/lean4/blob/f3b06c705e6c85f5314019d5d3baab0fec5b580c/src/Std/Tactic/BVDecide/Reflect.lean#L174-L203): `verifyCert`, `verifyCert_correct`, `verifyBVExpr`, and `unsat_of_verifyBVExpr_eq_true`; [`Std/Tactic/BVDecide/LRAT/Checker.lean`](https://github.com/leanprover/lean4/blob/f3b06c705e6c85f5314019d5d3baab0fec5b580c/src/Std/Tactic/BVDecide/LRAT/Checker.lean#L30-L49): `check` and `check_sound`; [`Lean/Meta/Tactic/BVDecide/Prover/Bitblast.lean`](https://github.com/leanprover/lean4/blob/f3b06c705e6c85f5314019d5d3baab0fec5b580c/src/Lean/Meta/Tactic/BVDecide/Prover/Bitblast.lean#L26-L115): `LratCert.toReflectionProof`, `lratBitblaster`, and `lratChecker`; official tag `v4.32.2` resolves to the cited commit | `leanBVDecide432` |

## Scope decisions

- Brown's transcription and OEIS motivate historical context only; neither is
  used to establish an equation in the artifact.
- The CSP references justify the bounded-interface method in general; the
  artifact's concrete frontier still requires direct verification.
- The DRAT, LRAT, FRAT, and CaDiCaL references describe possible certificate
  formats and solver interfaces. They do not by themselves establish that this
  artifact emits such a trace.
- The Lean source row supports the implementation-level description at exactly
  the frozen toolchain commit. It is not a claim that arbitrary external solver
  output is trusted without checking.
- No literature-absence or priority claim is supported by this matrix.
