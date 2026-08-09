# Textbook-Style Base-19 Preprint Design

Date: 2026-08-08

Author pseudonym: 8128

Status: approved design awaiting written-spec review

## Purpose

Produce a standalone, submission-quality mathematical preprint explaining the
fixed base-19 reverse-and-add obstruction, its deletion-minimal computational
core, and the new proof-producing Lean/LRAT check. The exposition should read
like a concise textbook chapter while retaining the structure, precision, and
claim discipline expected of a research preprint.

The intended audience is balanced: number theorists should be able to follow
the formal-verification material, and formal-methods researchers should be
able to understand the reverse-and-add mathematics without specialist
background.

## Deliverable

Create a separate preprint candidate rather than overwriting the released
five-page paper. The candidate consists of LaTeX source, bibliography,
generated quantitative data where appropriate, a reproducible build script,
and a built PDF. The expected length is 10--12 pages, including references and
a compact reproducibility appendix.

The title is:

> A Proof-Producing Base-19 Obstruction in a Reverse-and-Add Constraint System

The title page and PDF metadata identify the author as `8128`.

## Mathematical Claim Structure

The paper distinguishes four statements.

1. The frozen 409-equation candidate is computationally unsatisfiable by exact
   radial-frontier replay.
2. Removing `phase=0,n=0,column=82` gives a 408-equation core that is
   computationally unsatisfiable, while every single-equation deletion of
   that core has a replayed satisfying assignment. This is deletion
   minimality, not minimum cardinality.
3. The exact six-bit packed encoding of the 408-equation core is unsatisfiable
   by the Lean theorem `Base19Radial.packedMinimalCoreUnsat`, generated through
   `bv_decide` and an LRAT certificate.
4. The packed encoding and bounded integer equations are mathematically
   equivalent because digit slots are below 19, carry slots are below 2, the
   six leading digits are nonzero, and each side of a column equation is at
   most 37, below the six-bit modulus 64.

Statement 3 is proof-producing and Lean checked, but it is not described as a
kernel-reduction-only theorem. Its exact reported dependencies include
`propext`, `Classical.choice`, `Quot.sound`, and the generated native
certificate-evaluation axiom
`packedMinimalCoreUnsat._native.bv_decide.ax_1_5`. Statement 4 is a paper
proof unless a formal bridge is implemented separately; this preprint does
not silently claim such a bridge already exists in Lean.

## Scope and Non-Claims

The preprint does not claim:

- a base-19 Lychrel number;
- a resolution of OEIS A060382;
- uniqueness of the obstruction outside the audited one-deletion family;
- a minimum-cardinality unsatisfiable core;
- an all-base theorem;
- a strict kernel-reduction-only proof of the concrete UNSAT result; or
- a theorem about the unbounded reverse-and-add process.

These limitations appear in the abstract, the main theorem discussion, a
dedicated trust-boundary box, and the conclusion.

## Expository Organization

1. **Orientation.** Begin with a small base-10 reverse-and-add example and
   derive one column equation. State the finite scope before discussing the
   motivating conjectural context.
2. **The frozen base-19 system.** Define digits, carries, phases, words,
   retained coordinate bands, the candidate, and the 408-equation core.
3. **Radial decomposition.** Explain live variables, frontier states, local
   transitions, and empty-frontier soundness. Include a radial-propagation
   diagram and the generic Lean soundness theorem.
4. **Deletion-minimal obstruction.** Present the exact replay, the complete
   deletion audit, measured frontier width, and the distinction between
   deletion minimality and minimum size.
5. **Packed finite encoding.** Define the 4,914-bit assignment as 819 six-bit
   slots, give the no-overflow lemma, and prove on paper that bounded integer
   models correspond to packed models.
6. **Proof-producing Lean/LRAT check.** State the packed theorem, explain
   bit-blasting, CaDiCaL certificate search, LRAT checking, runtime, memory,
   manifest binding, and exact theorem dependencies.
7. **Assurance ladder.** Compare exact Z3 replay, verified LRAT checking with
   native evaluation, and the unclaimed kernel-reduction-only endpoint.
8. **Reproducibility and limitations.** Give immutable identifiers, commands,
   dependency versions, and conservative interpretation.
9. **Related work and conclusion.** Situate the method without using related
   work as a premise. End with the precise bounded finding.
10. **Compact appendix.** Record theorem names, hashes, and commands without
    reproducing large certificates or generated source.

## Visual System

Use a restrained mathematical-textbook design that remains recognizable as a
research preprint:

- conventional letter-size article geometry and two-sided running headers;
- a serif text family with coordinated mathematics;
- dark navy section headings and muted teal accents on a warm off-white page;
- grayscale-safe contrast and no meaning encoded by color alone;
- numbered definitions, lemmas, theorems, propositions, examples, and remarks;
- lightly shaded `Key idea`, `Trust boundary`, and `What this does not prove`
  boxes;
- generous equation spacing, compact booktabs tables, and restrained use of
  marginal or inline labels;
- a table of contents and page-numbered running footer; and
- no stock imagery or decorative mathematics unrelated to the result.

Create two original vector diagrams in TikZ:

1. a schematic radial frontier showing layers, live interfaces, and the empty
   terminal frontier; and
2. an assurance ladder showing the distinct trusted bases of computational
   replay, Lean/LRAT native evaluation, and strict kernel reduction.

The diagrams are explanatory and do not serve as proof evidence.

## Citation and Attribution Policy

Every theorem, algorithm, historical statement, or implementation not
originating in this artifact receives a nearby citation. Prefer primary or
authoritative sources. At minimum, verify and cite sources for:

- Seal's base-17 construction and Brown's account;
- OEIS A060382 as conjectural context only;
- reverse-and-add and Lychrel terminology;
- path decomposition and bounded-width constraint satisfaction;
- Z3 and its linear-integer arithmetic procedure;
- Lean 4 and its trust model;
- LRAT and verified certificate checking;
- CaDiCaL; and
- Lean's `bv_decide` implementation and LRAT checker.

Artifact-specific claims cite frozen paths, hashes, theorem names, or generated
tables instead of presenting them as external literature. Bibliographic
metadata is checked against primary sources. The paper does not cite a source
for a stronger claim than that source actually supports.

## Data and Build Flow

The paper sources quantitative values from the frozen artifact rather than
manually duplicating them where practical. The generation flow is:

```text
frozen equation and certificate JSON
            +
Lean theorem source and axiom output
            |
            v
generated LaTeX result macros
            |
            v
preprint source + verified bibliography
            |
            v
pinned TeX build -> candidate PDF
```

The candidate uses the existing digest-pinned TeX environment. Its build
script sets deterministic date and timezone inputs, rejects missing citations
or references, rejects overfull boxes, and requires a nonempty PDF.

## Validation

Validation is proportional to a submission candidate:

1. regenerate quantitative macros and compare them byte-for-byte;
2. build the PDF from a clean output directory in the pinned environment;
3. fail on unresolved citations, unresolved references, or overfull boxes;
4. inspect PDF metadata, page count, embedded fonts, and extracted text;
5. render every page to images and inspect them for clipping, bad breaks,
   illegible diagrams, sparse pages, and inconsistent visual rhythm;
6. verify every artifact hash and theorem name printed in the paper;
7. audit the abstract, theorem statements, conclusion, and captions against the
   assurance labels in this design; and
8. run the relevant publication tests without changing the released paper.

The candidate is not promoted over the released preprint until the user
reviews the PDF and explicitly accepts replacement.

## Failure Handling

- If a primary citation cannot be verified, omit or narrow the associated
  claim rather than citing a secondary source as stronger evidence.
- If the pinned TeX image lacks a desired visual package or font, use a simpler
  package already present rather than adding an unpinned dependency.
- If a quantitative value cannot be generated from frozen evidence, identify
  it explicitly as prose or a measured development-machine result.
- If the PDF cannot meet the 10--12 page target without crowding, prefer up to
  14 readable pages over smaller type or compressed mathematics.
- If any assurance statement becomes ambiguous, use the weaker accurate label.

## Acceptance Criteria

The design is successful when:

- a mathematically literate reader can reconstruct the problem, core result,
  packed encoding, and trust boundary without consulting the repository;
- the preprint presents the bounded finding as real without implying a general
  Lychrel theorem;
- all non-original work is appropriately cited;
- the PDF is visually consistent, readable, and suitable for public preprint
  review;
- the build and generated values are reproducible; and
- the released paper remains untouched pending explicit acceptance.
