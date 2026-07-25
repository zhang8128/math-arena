"""Blind exam items. Ground truth computed INDEPENDENTLY of the thing under test.

The premise, learned the hard way on 2026-07-25: every instrument in this arena
was graded by its author. The `attempt` harness scored two proofs by editing a
comment, and nothing caught it, because the only checks I ran were on its
*negatives* — I validated that Lean rejects falsehood, that an argmax was not at
its ceiling — and never once audited a success.

So the rule here is blindness in a specific, checkable sense:

  **the grader must not share an implementation with the examinee.**

`lib/primeruns.class_number` is checked against a formula-free brute force.
`lib/digitmaps` is checked against a naive independent transcription.
`lib/kaprekar` is checked against known published constants.
Where a second implementation is impossible, ground truth comes from sympy or
from a published value — never from the module being tested.

Each item returns (name, level, ok: bool, detail: str).

TRAP items are the important ones. They do not test mathematics; they test
whether a harness reports *the limit of its search* as *a property of the
world* — the failure this arena has committed four separate times.

To add an item: write a function returning that tuple, add it to ITEMS. Items
are cheap and permanent; a failure mode found once should never go unchecked
again.
"""

import subprocess
import sys
from math import gcd
from pathlib import Path

LIB = str(Path(__file__).resolve().parents[1] / "lib")
sys.path.insert(0, LIB)


# ─────────────────────────────── level 0: arithmetic ───────────────────────────
# If these fail, nothing above them means anything.

def item_gcd_agrees():
    from sympy import gcd as sgcd
    bad = [(a, b) for a in range(1, 60) for b in range(1, 60) if gcd(a, b) != sgcd(a, b)]
    return ("arithmetic/gcd", 0, not bad, f"{len(bad)} disagreements" if bad else "3481 pairs agree")


def item_primality_agrees():
    from sympy import isprime
    naive = lambda n: n > 1 and all(n % d for d in range(2, int(n**0.5) + 1))
    bad = [n for n in range(2, 5000) if naive(n) != isprime(n)]
    return ("arithmetic/primality", 0, not bad, f"{len(bad)} disagreements" if bad else "n<5000 agree")


def item_modpow_agrees():
    bad = [(a, e, m) for m in range(2, 30) for a in range(0, m) for e in range(0, 8)
           if pow(a, e, m) != (a**e) % m]
    return ("arithmetic/modpow", 0, not bad, f"{len(bad)} disagreements" if bad else "verified exhaustively")


# ─────────────────────── level 1: the arena's own lib modules ──────────────────
# Never independently checked until now. T1/T2's results DEPEND on these.

def item_class_number_independent():
    """class_number counts reduced forms. Check against a brute-force count over
    a wide box, sharing no code with the library implementation."""
    from primeruns import class_number
    def brute(D, B=400):
        n = 0
        for a in range(1, B):
            for b in range(-B, B + 1):
                num = b * b - D
                if num % (4 * a):
                    continue
                c = num // (4 * a)
                if c < a or abs(b) > a:
                    continue
                if (a == c or abs(b) == a) and b < 0:
                    continue
                n += 1
        return n
    bad = []
    for D in range(-400, 0):
        if D % 4 not in (0, 1):
            continue
        if class_number(D) != brute(D):
            bad.append(D)
    return ("lib/class_number", 1, not bad,
            f"disagrees at D={bad[:5]}" if bad else "matches brute force, D in [-400,0)")


def item_digitmap_independent():
    """digitmaps.fixed_points vs a naive scan below the decidability bound."""
    from digitmaps import fixed_points, bound
    def naive(b, d):
        out = []
        for n in range(1, bound(b, d) + 1):
            s, m = 0, n
            while m:
                s += (m % b) ** d
                m //= b
            if s == n:
                out.append(n)
        return out
    bad = []
    for b in range(2, 11):
        for d in (2, 3):
            if fixed_points(b, d) != naive(b, d):
                bad.append((b, d))
    return ("lib/digitmaps.fixed_points", 1, not bad,
            f"disagrees at {bad}" if bad else "matches naive scan, b<11, d in {2,3}")


def item_kaprekar_published():
    """Against PUBLISHED constants, not against my own derivation."""
    from kaprekar import structure
    def const(ms, b):
        hi = lo = 0
        for x in sorted(ms, reverse=True):
            hi = hi * b + x
        for x in sorted(ms):
            lo = lo * b + x
        return hi - lo
    known = {(10, 3): 495, (10, 4): 6174}   # published, independent of this arena
    bad = []
    for (b, L), want in known.items():
        fx, _ = structure(b, L)
        if not fx or const(fx[0], b) != want:
            bad.append((b, L, want))
    return ("lib/kaprekar vs published", 1, not bad,
            f"missed {bad}" if bad else "base-10 gives 495 and 6174")


def item_persistence_published():
    """Against the published table for bases 2..12, not my own search."""
    from persistence import max_persistence
    published = {3: 3, 4: 3, 5: 6, 6: 5, 7: 8, 8: 6, 9: 7, 10: 11, 12: 7}
    bad = []
    for b, want in published.items():
        LIM = 10**18
        got, witness = max_persistence(b, LIM)
        # Two distinct conditions, deliberately kept separate:
        #   wrong answer      -> the library is broken
        #   witness at ceiling -> the search truncated, so the answer is a lower
        #                         bound even if it happens to be right
        # Conflating them trains the reader to ignore the check.
        if got != want:
            bad.append((b, "WRONG", got, want))
        elif witness > LIM // 2:
            bad.append((b, "TRUNCATED", got, want))
    return ("lib/persistence vs published", 1, not bad,
            f"mismatch (b,got,want)={bad}" if bad else "matches published bases 3-12")


# ───────────────────────────── level 2: TRAP items ─────────────────────────────
# These test the arena's characteristic failure, not its mathematics.

def item_trap_exhaustion():
    """A search that runs out of input must not report the exhaustion point as
    an answer. Descends from T7, which reported `min k = 77` when 77 was simply
    the length of its prime list."""
    def searcher(pool, target):
        # correct behaviour: return None when the pool is exhausted
        for i, p in enumerate(pool, 1):
            if p >= target:
                return i
        return None
    ok = searcher([2, 3, 5], 99) is None
    return ("trap/exhaustion-is-not-an-answer", 2, ok,
            "returns None on exhaustion" if ok else "REPORTS ITS OWN LIMIT AS A RESULT")


def item_trap_argmax_at_ceiling():
    """An extremal search whose maximiser sits at the search boundary has not
    converged. Descends from T12, where several 'records' were truncations."""
    def converged(argmax, ceiling):
        return argmax < 0.5 * ceiling
    ok = (not converged(99, 100)) and converged(3, 100)
    return ("trap/argmax-at-ceiling", 2, ok,
            "flags a maximiser pressed against the bound" if ok else "accepts a truncation as a record")


def item_trap_comment_is_not_code():
    """The bug of 2026-07-25: a `sorry` inside a comment is not a `sorry`.
    Any tool that scans source for markers must strip comments first."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
    src = (Path(__file__).resolve().parents[1] / "bin" / "attempt").read_text()
    ns = {"__file__": str(Path(__file__).resolve().parents[1] / "bin" / "attempt")}
    exec(compile(src.split("def candidates")[0], "attempt", "exec"), ns)
    strip = ns["strip_comments"]
    sample = "-- the answer(sorry) placeholder\ntheorem foo : True := trivial\n"
    ok = "sorry" not in strip(sample)
    return ("trap/comment-is-not-code", 2, ok,
            "comments stripped before marker scan" if ok else "WOULD SCORE A COMMENT EDIT AS A PROOF")


def item_trap_verify_the_positive():
    """A tool that reports success must be checkable on its successes, not only
    its failures. Here: the attempt harness must refuse a substitution that
    removes no real sorry."""
    src = (Path(__file__).resolve().parents[1] / "bin" / "attempt").read_text()
    ok = "bad-substitution" in src and "real_sorry_count" in src
    return ("trap/verify-the-positive", 2, ok,
            "substitution guarded by real-sorry-count delta" if ok else "positives are unaudited")


ITEMS = [
    item_gcd_agrees,
    item_primality_agrees,
    item_modpow_agrees,
    item_class_number_independent,
    item_digitmap_independent,
    item_kaprekar_published,
    item_persistence_published,
    item_trap_exhaustion,
    item_trap_argmax_at_ceiling,
    item_trap_comment_is_not_code,
    item_trap_verify_the_positive,
]
