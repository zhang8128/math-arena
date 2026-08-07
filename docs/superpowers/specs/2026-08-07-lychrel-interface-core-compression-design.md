# T26 Lychrel Interface-Core Compression — Design

## Goal and claim boundary

Explain T25's eight phase-zero topology obstructions with small sets of exact
`n=0` addition columns.  For every moved topology and base `18..40`, retain
arbitrary fixed digits in `0..B-1`, canonical leading digits, fixed repeat
digits `0` and `B-1`, and fresh Boolean carries.  Extract column-level
group-unsatisfiable cores, organize repeating coordinate sets into families,
and replay every claimed family with an implementation that imports neither
the one-hot compiler nor the SAT-core extractor.

The primary target is a deletion-irreducible group core: the selected columns
are jointly UNSAT while deleting any one selected column makes the system SAT,
with digit domains and leading-nonzero constraints treated as permanent hard
constraints.  This is not a minimum-cardinality claim.  A symbolic uniform
obstruction is reported only if an explicit independently checked derivation
is found; similarity among coordinate sets is not itself a theorem.

T26 does not search new topologies, new bases, or new Lychrel seeds.  If no
small/shared core appears, the honest result is a measured proof-compression
failure together with exact irreducible cores for the instances reached.

## Grouped exact encoding

Extend the deterministic one-hot compiler with a grouped form.  Domain clauses
for all 497 digit occurrences and the six leading-nonzero clauses are hard.
Every implication generated from one `ColumnConstraint` belongs to the group
named by that column's provenance.  Give each group a fresh selector `s_g` and
guard every clause `C` as `not s_g or C`.  Assuming `s_g` activates exactly
that column; omitting the assumption lets the selector disable it.

The grouped compiler must preserve the unguarded T25 formula under all
selectors set true.  Tests compare literal clauses after stripping selectors,
check stable group order and digest, and use small hand-derived formulas where
known column subsets are SAT or UNSAT.  This prevents a core extractor from
silently changing the mathematical problem.

## Primary core extraction

Use CaDiCaL 3.0.1 through its installed C++ API (`cadical.hpp` and
`libcadical.a`).  Its documented incremental interface supports
`assume(literal)` and `failed(literal)`.  Full one-hot selector extraction was
measured and rejected after two bounded trials: freezing 499 selectors blocked
useful preprocessing, while restoration-based assumptions still failed to
finish the first base-18 seed in four minutes even though the corresponding
unguarded formula solved in 1.69 seconds.

The primary extractor therefore uses two calibrated encodings of the same
named columns.  The compact T25 binary full-adder encoder supplies an initial
failed-assumption seed and performs deletion minimization.  The deterministic
one-hot encoder then replays the exact resulting provenance set and every
deletion.  Both encodings retain all digit domains and leading constraints as
hard clauses.  A small tracked C++ executable:

1. parses one grouped DIMACS formula and its ordered selector list;
2. assumes requested groups in `seed` and `verify` modes;
3. requires an exact SAT or UNSAT result;
4. in `seed` mode, retains assumptions reported by `failed`;
5. in `extract` mode, uses deterministic chunk deletion followed by exact
   deletion batches over fresh, fully preprocessed solvers; and
6. in `verify` mode, rechecks joint UNSAT and every one-group deletion under
   incremental assumptions before emitting JSON.

The executable's output identifies solver version, input digest, selected
groups, status, and deletion witnesses.  UNKNOWN, malformed input, selector
misalignment, or a failed irreducibility check stops evidence generation.

Broad seeds may use eight parallel deletion workers.  A batch removes only the
first canonical group whose deletion is independently UNSAT, then restarts;
an all-SAT batch proves deletion irreducibility.  Scheduling cannot affect the
chosen core.  This is a group MUS over columns, not a clause MUS.  Learned
clauses and failed-core membership guide search but do not enter the durable
certificate; the original selected column constraints are replayed in both
CNF representations and again by the independent path.

## Family discovery and bounded coverage

For each of the eight phase-zero variants, begin at base 18 and extract one
deletion-irreducible core.  Test that exact provenance set in every base
`18..40`.  If it fails to prove UNSAT in some base, choose the least uncovered
base as the next representative, extract another core, and repeat until all 23
bases are covered or a fail-closed error occurs.

This representative-first loop avoids 184 independent MUS extractions while
remaining complete over the bounded matrix.  Each family records:

- the variant, representative base, and exact column provenances;
- all bases where the same columns are jointly UNSAT;
- joint and one-column-deletion statuses for every covered base;
- canonicalized digit/carry incidence and stable digests; and
- bases left for later families.

Coordinate sets are canonicalized across moved fragment partitions by mapping
each fixed occurrence to `(phase, flattened_fixed_index)`.  Carries retain
their `(phase,column)` identity.  Families may be merged across variants only
when canonical constraints, not merely provenance strings, agree.

## Independent finite-domain replay

A standalone Python script reads only T21 JSON and the serialized T26 core
families.  It independently moves the phase-zero interface, renders the named
columns, and enforces

`left + right + carry_in = target + B*carry_out`

with digit domains `0..B-1`, Boolean carries, and canonical leading digits.
It uses deterministic domain propagation plus backtracking over the smallest
remaining domain; it imports no T24/T25/T26 production module and invokes no
SAT solver.

For every family/base pair, the checker must find zero joint assignments and
at least one explicit satisfying assignment, projected to the variables used
by the remaining core, after deleting each selected column.  Every witness is
replayed arithmetically before acceptance.  This
establishes deletion-irreducibility independently and makes the mathematical
certificate inspectable without trusting learned clauses or selector logic.

If a core is too large for bounded independent replay, it is not promoted as
an explanatory result.  Record the resource failure and continue searching
for a smaller family or stop without a core claim.

## Symbolic obstruction test

After exact family coverage, compare the independently rebuilt constraints.
Attempt a uniform explanation only when the same canonical family covers at
least two variants or all 23 bases for one variant.  Eliminate private digit
and carry variables by exact finite-domain support propagation, record each
forced domain reduction, and test whether the contradiction can be stated as
an integer equality/inequality valid for the claimed base interval.

Any proposed symbolic statement must be checked in two ways: direct exhaustive
replay for every base `18..40`, and a separate algebraic derivation whose steps
do not call the SAT solver.  Passing the finite range alone is described as
bounded coverage, not an all-base theorem.  If elimination yields no concise
derivation, preserve the core families and say so.

## Alternatives considered

### DRAT/LRAT proof slicing

CaDiCaL can emit proof traces and checked traces would strengthen the global
UNSAT evidence.  However, no DRAT/LRAT checker is installed, a proof dependency
slice is not automatically a column MUS, and adding that toolchain would mix
two goals.  T26 targets human-scale constraint explanations; proof traces
remain a later certification project.

### MARCO or full MUS enumeration

MARCO-style algorithms use MUS/MSS duality and are appropriate for enumerating
many explanations, but the number of MUSes may be exponential.  T26 needs one
checked family cover, not exhaustive MUS enumeration.  Representative-first
extraction is the smaller, falsifiable experiment.

### Fixed boundary windows

Expanding windows around moved repeat positions is intuitive but assumes the
contradiction is local.  Incidence localization is a conclusion to measure
from extracted cores, not a search restriction.

## Prism and research disposition

Prism applied duality and graph/hypergraph frames to immutable problem
`lychrel-interface-unsat-core-compression`, version 1, seed `20260807`, using
`qwen3.6:27b-mlx`.  Both applications were schema-invalid and produced zero
artifacts.  No Prism claim enters the design or later frame evolution.

The selected method is consistent with established group-MUS practice:
selector assumptions expose constraint groups, failed assumptions seed a
core, and deletion checks establish subset minimality.  The design explicitly
separates an irreducible MUS from a minimum-cardinality core.  Relevant method
sources include CaDiCaL's documented incremental API and Liffiton et al.'s
MARCO/MUS work; they justify tools, not the mathematical result.

## Evidence, tests, and stop conditions

The deterministic T26 artifact records grouped-formula calibration, CaDiCaL
build/version, representative extraction history, family coverage, all
deletion checks, independent CSP results and witnesses, canonical incidence
digests, Prism invalid application IDs, and precise limitations.

Stop and report rather than weaken the claim when:

- the guarded and unguarded formulas do not calibrate exactly;
- any extraction or coverage solve returns UNKNOWN;
- primary and independent joint/deletion statuses disagree;
- an independent deletion witness fails arithmetic replay;
- full bounded coverage is incomplete; or
- a symbolic claim is proposed but does not survive both checks.

Success has two levels.  Level one is complete, independently replayed core
families covering all eight variants and bases `18..40`.  Level two is a
concise symbolic boundary obstruction with an explicit independently checked
derivation.  Level one is a valid result even if level two is not reached.
