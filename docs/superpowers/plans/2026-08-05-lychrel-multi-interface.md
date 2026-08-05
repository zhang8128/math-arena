# Lychrel Multi-Interface Word Proof Implementation Plan

> **Execution mode:** The user selected isolated inline execution, so this plan was completed without delegated workers. Steps use checkbox syntax for tracking.

**Goal:** Build and exercise a finite symbolic verifier for reverse-add cycles whose states contain any number of independently growing `0^n` or `(b-1)^n` blocks, calibrated by reconstructing David Seal's published base-17 certificate.

**Architecture:** Represent a parametric digit word as fixed digit fragments separated by homogeneous repeat blocks. Compile its numeric value to an exact polynomial in `q=b^n`; reversal is token reversal, and a complete reverse-add induction is coefficient equality, with `q -> bq` on the wraparound step. A separate inference layer proposes templates from two finite orbit cycles, while the polynomial layer independently accepts or rejects them.

**Tech Stack:** Python 3.14 standard library, immutable dataclasses, integer coefficient arithmetic, pytest, existing `.timeloop` arena conventions.

## Global Constraints

- Preserve the user-owned `.timeloop/exam/results.jsonl` modification untouched.
- Add no runtime dependency and do not require GHC, Sage, SMT, or a network service.
- Treat Prism artifacts and finite orbit patterns only as hypotheses; only exact coefficient identities certify a recurrence.
- A certified cycle must include an all-`n` non-palindrome witness for every phase.
- Report graph or orbit cutoffs exactly; never describe a bounded scan as exhaustive.

---

### Task 1: Exact parametric-word algebra

**Files:**
- Create: `.timeloop/lib/lychrel_wordproof.py`
- Create: `.timeloop/tests/test_lychrel_wordproof.py`

**Interfaces:**
- Consumes: digit tuples with entries in `range(base)`.
- Produces: `ParametricWord`, `render`, `reversed_word`, `value_polynomial`, `shift_parameter`, `reverse_add_digits`, and `verify_cycle`.

- [x] **Step 1: Write failing polynomial and cycle tests**

```python
def test_two_interface_word_compiles_to_exact_values() -> None:
    word = ParametricWord(5, ((1,), (2,), (3,)), (0, 4))
    polynomial = value_polynomial(word)
    for n in range(5):
        assert evaluate_polynomial(polynomial, 5**n) == digits_value(word.render(n), 5)


def test_reverse_add_cycle_requires_shift_on_wraparound() -> None:
    assert verify_cycle(published_binary_cycle())
```

- [x] **Step 2: Run the tests and confirm failure due to the missing module**

Run: `pytest -q .timeloop/tests/test_lychrel_wordproof.py`

Expected: collection error naming `lychrel_wordproof`.

- [x] **Step 3: Implement immutable words and polynomial compilation**

```python
@dataclass(frozen=True)
class ParametricWord:
    base: int
    fragments: tuple[tuple[int, ...], ...]
    repeats: tuple[int, ...]

    def render(self, n: int) -> tuple[int, ...]:
        if n < 0:
            raise ValueError("n must be nonnegative")
        result = list(self.fragments[0])
        for repeat, fragment in zip(self.repeats, self.fragments[1:]):
            result.extend((repeat,) * n)
            result.extend(fragment)
        return tuple(result)


def value_polynomial(word: ParametricWord) -> tuple[int, ...]:
    # Fixed fragment F: P <- b^len(F) P + value(F).
    # Repeat 0^n:       P <- q P.
    # Repeat (b-1)^n:   P <- q P + q - 1.
    polynomial = (0,)
    for index, fragment in enumerate(word.fragments):
        polynomial = add_constant(
            scale(polynomial, word.base ** len(fragment)),
            digits_value(fragment, word.base),
        )
        if index < len(word.repeats):
            polynomial = multiply_by_q(polynomial)
            if word.repeats[index] == word.base - 1:
                polynomial = add_polynomials(polynomial, (-1, 1))
    return trim(polynomial)
```

`verify_cycle(words)` must check `W_r + rev(W_r) = W_(r+1)` coefficient-wise for ordinary phases and `W_last + rev(W_last) = W_0(n+1)` by substituting `q -> bq` for the wraparound phase.

- [x] **Step 4: Run the focused tests and confirm they pass**

Run: `pytest -q .timeloop/tests/test_lychrel_wordproof.py`

Expected: all Task 1 tests pass.

### Task 2: Template inference kept outside the verifier

**Files:**
- Modify: `.timeloop/lib/lychrel_wordproof.py`
- Modify: `.timeloop/tests/test_lychrel_wordproof.py`

**Interfaces:**
- Consumes: two concrete digit words believed to be `W(0)` and `W(1)`.
- Produces: `infer_words(base, small, large, max_blocks=4) -> tuple[ParametricWord, ...]` and `infer_cycle(base, first, second, max_blocks=4) -> tuple[ParametricWord, ...] | None`.

- [x] **Step 1: Write failing inference tests**

```python
def test_inference_enumerates_ambiguous_repeat_boundaries() -> None:
    candidates = infer_words(5, (1, 0, 2, 4, 3), (1, 0, 0, 2, 4, 4, 3))
    assert candidates
    assert all(word.render(0) == (1, 0, 2, 4, 3) for word in candidates)
    assert all(word.render(1) == (1, 0, 0, 2, 4, 4, 3) for word in candidates)
```

- [x] **Step 2: Run the new test and confirm the missing-symbol failure**

Run: `pytest -q .timeloop/tests/test_lychrel_wordproof.py -k inference`

Expected: failure naming `infer_words`.

- [x] **Step 3: Implement deletion-alignment inference and algebraic filtering**

Enumerate every alignment obtained by deleting exactly `len(large)-len(small)` digits from `large`, retaining only deleted digits in `{0, base-1}` and at most four deletions. Convert each deletion alignment into fixed fragments plus one repeat token per deleted digit. Deduplicate immutable words. `infer_cycle` must retain only phase combinations accepted by `verify_cycle`; it must not use further numerical samples as its acceptance rule.

- [x] **Step 4: Run all focused tests**

Run: `pytest -q .timeloop/tests/test_lychrel_wordproof.py`

Expected: all Task 1 and Task 2 tests pass.

### Task 3: Reconstruct and certify the published base-17 family

**Files:**
- Modify: `.timeloop/tests/test_lychrel_wordproof.py`
- Create: `.timeloop/runs/t21_lychrel_multi_interface.py`

**Interfaces:**
- Consumes: Seal's phase-zero word `A 0^n B 16^n C` and exact digitwise reverse-add.
- Produces: a six-phase inferred certificate, coefficient identities, fixed outer-digit palindrome mismatches, and JSON evidence.

- [x] **Step 1: Write the failing calibration test**

```python
def test_base17_published_family_is_inferred_and_certified() -> None:
    first_cycle, second_cycle = base17_sample_cycles(n=2)
    certificate = infer_cycle(17, first_cycle, second_cycle, max_blocks=2)
    assert certificate is not None
    assert verify_cycle(certificate)
    assert all(fixed_palindrome_mismatch(word) is not None for word in certificate)
```

- [x] **Step 2: Run the calibration test and observe the expected missing fixture or mismatch failure**

Run: `pytest -q .timeloop/tests/test_lychrel_wordproof.py -k base17 -vv`

Expected: failure before the base-17 fixture and inference integration exist.

- [x] **Step 3: Implement the base-17 fixture and evidence script**

The script must:

1. parse the published fragments with alphabet `0123456789abcdefg`;
2. create phase zero for `n=2` and `n=3`;
3. independently generate both six-step cycles by digitwise addition;
4. assert the first cycle's sixth state equals the second cycle's first state;
5. infer all six templates from corresponding states;
6. accept them only through exact polynomial identities;
7. output each template, coefficient identity, and a fixed palindrome mismatch.

- [x] **Step 4: Run the base-17 calibration and tests**

Run: `python3 .timeloop/runs/t21_lychrel_multi_interface.py --calibrate-base17`

Expected: JSON with `period: 6`, `interfaces: 2`, `verified: true`, and six non-palindrome witnesses.

Run: `pytest -q .timeloop/tests/test_lychrel_wordproof.py`

Expected: all focused tests pass.

### Task 4: Bounded self-similar recurrence scan and durable result

**Files:**
- Modify: `.timeloop/runs/t21_lychrel_multi_interface.py`
- Modify: `.timeloop/notebook/lychrel-bases.md`
- Modify: `.timeloop/ledger.md`
- Modify: `.timeloop/pool.jsonl` only if the target's next technique changes.
- Create: `.timeloop/runs/t21_lychrel_multi_interface.json`

**Interfaces:**
- Consumes: one orbit per selected base, exact digitwise reverse-add, periods `2..12`, and at most four inserted homogeneous-interface digits.
- Produces: independently verified parametric certificates or an exact bounded negative census.

- [x] **Step 1: Write a failing scanner control test**

```python
def test_scanner_detects_base17_control_at_period_six() -> None:
    orbit = base17_control_orbit(n=2, steps=13)
    hits = scan_recurrences(17, orbit, periods=range(2, 13), max_blocks=4)
    assert [(hit.start, hit.period) for hit in hits] == [(0, 6)]
```

- [x] **Step 2: Run the scanner test and confirm failure because `scan_recurrences` is absent**

Run: `pytest -q .timeloop/tests/test_lychrel_wordproof.py -k scanner`

Expected: failure naming `scan_recurrences`.

- [x] **Step 3: Implement the bounded scanner with cheap prefilters**

Only invoke template inference when every corresponding phase pair has the same positive length increase, the increase is at most four, and the shorter word is a subsequence of the longer after deleting only `0` or `b-1`. Every reported hit must pass `verify_cycle` and six/all-period fixed palindrome mismatch checks.

- [x] **Step 4: Run the control and bounded unknown-base scan**

Run: `python3 .timeloop/runs/t21_lychrel_multi_interface.py --scan --min-base 3 --max-base 40 --steps 1200 --max-period 12 --max-blocks 4 > .timeloop/runs/t21_lychrel_multi_interface.json`

Expected: the JSON records every base, seed, step and period bound, the base-17 positive control, and each exact certificate or zero-hit result.

- [x] **Step 5: Perform mandatory novelty checking for every survivor**

Search exact base, seed, period, and template fragments in OEIS and primary/public web sources. If there is no survivor, record the bounded negative without a novelty claim.

- [x] **Step 6: Update the notebook and append one ledger line**

Record STATUS, SEARCHED, RULED OUT, STRUCTURE, TECHNIQUE, NOVELTY, NEXT, and COST. Explicitly separate algebraically certified hits, known published controls, and bounded no-hit bases.

- [x] **Step 7: Run final verification**

Run:

```bash
python3 -m py_compile .timeloop/lib/lychrel_wordproof.py .timeloop/runs/t21_lychrel_multi_interface.py
python3 -m json.tool .timeloop/runs/t21_lychrel_multi_interface.json >/dev/null
pytest -q .timeloop/tests
git diff --check
```

Expected: compilation and JSON validation succeed, the complete arena test suite passes, and `git diff --check` emits no output.
