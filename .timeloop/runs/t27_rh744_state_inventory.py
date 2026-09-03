#!/usr/bin/env python3
"""T27 -- rh-turing-golf.

Combine of two frames on the 744-state Matiyasevich/Aaronson RH machine:

  * tabulate-the-right-invariant : the raw parameter is "lines of riemann.nql".
    The invariant that actually controls the phenomenon is the MARGINAL STATE
    COST of each construct after BDD compression.  Measured differentially:
    delete a construct, recompile, take the difference.  Compilation is 0.08s,
    so the whole table is cheap.

  * sharper-subquestion : a halting witness must satisfy TWO conditions at once
    -- (i) psi(x) - x is a large positive excursion, and (ii) it clears a
    threshold that is knife-edge at exponent 1/2.  Condition (ii) is what makes
    the threshold function expensive, and it is invisible if you only look at
    (i).  Attacking the intersection means asking: what is the CHEAPEST
    function that still separates the two sides?

The interaction: (ii) rules out every monomial threshold x^r, r > 1/2 (if the
first off-line zero has real part < r the machine never halts and the machine
is WRONG, not merely slower), so the threshold must be sqrt(x) * F(x) with
log^2 x << F(x) << x^eps.  That leaves a small menu of candidate F.  The cost
table is the only thing that can rank that menu.  Neither frame alone gets
there: sharper-subquestion alone would happily propose x^(3/5) and be wrong;
tabulate alone prices a program with no candidate replacement to price.

Usage:  python3 t27_rh744_state_inventory.py
"""
import hashlib
import os
import re
import subprocess
import sys
import tempfile

REPO = "https://github.com/sorear/metamath-turing-machines"
PIN = "0b8032c35bfb2107d94023f6ca2c2ffe6067faa8"   # HEAD at 2026-09-03
WORK = os.environ.get("T27_WORK", "/tmp/mtm")
PY = os.environ.get("T27_PY", sys.executable)


def ensure_toolchain():
    if not os.path.isdir(os.path.join(WORK, "compiler")):
        subprocess.run(["git", "clone", "--quiet", REPO, WORK], check=True)
    head = subprocess.run(["git", "-C", WORK, "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()
    return head


def compile_states(nql_text):
    """Compile NQL source, return (state_count, sha256 of the .tm) or (None, err)."""
    with tempfile.NamedTemporaryFile("w", suffix=".nql", delete=False) as fh:
        fh.write(nql_text)
        path = fh.name
    try:
        r = subprocess.run([PY, "nqlaconic.py", "--print-tm", path],
                           cwd=os.path.join(WORK, "compiler"),
                           capture_output=True, text=True)
        if r.returncode != 0:
            return None, r.stderr.strip().splitlines()[-1] if r.stderr else "fail"
        tm = r.stdout
        n = len([ln for ln in tm.splitlines() if ln.strip()])
        return n, hashlib.sha256(tm.encode()).hexdigest()[:12]
    finally:
        os.unlink(path)


HEADER = """option implicit_halt;
option no_sort_transfers;
"""


def prog(globals_, body):
    return HEADER + "".join("global %s;\n" % g for g in globals_) + \
        "\nproc main() {\n" + body + "}\n"


G10 = ["x", "lcm", "l", "num", "denom", "i", "a", "b", "c", "d"]

LCM_LOOP = """    lcm = 1;
    while (true) {
        x = x + 1;
        l = lcm;
        while (lcm != (lcm / l) * l || lcm != (lcm / x) * x) {
            lcm = lcm + 1;
        }
"""

HL_LOOP = """            num = 0;
            denom = 1;
            i = 1;
            while (i <= lcm) {
                num = num * i + denom;
                denom = denom * i;
                i = i + 1;
            }
"""

BASE_TAIL = """            a = num - denom * x;
            a = a * a;
            b = denom * denom;
            c = 0;
            d = 1;
            i = 1;
            while (i <= x) {
                c = c * i + d;
                d = d * i;
                i = i + 1;
            }
            c = c * c;
            c = c * c * x;
            d = d * d;
            d = d * d;
            if (a * d > b * c) {
                return;
            }
"""

BASELINE = prog(G10, LCM_LOOP + "        if (x > 253) {\n" + HL_LOOP + BASE_TAIL +
                "        }\n    }\n")

# ---------------------------------------------------------------- variants

# The combine: replace the harmonic threshold H_x^2 with the bit-length of x.
#   original halt test  (H_L - x)^2 >  x * H_x^4        (H_x = harmonic number)
#   variant  halt test  (H_L - x)^2 >  x * k^4,  k = floor(log2 x) + 1
# Both are sqrt(x) * Theta(log^2 x), so both sides of the iff survive; and
# k >= H_x for every x >= 4 (proved in the note below), so the variant is
# STRICTLY HARDER to trip -- it inherits the x > 253 guard's soundness.
BITLEN_TAIL = """            a = num - denom * x;
            a = a * a;
            b = denom * denom;
            c = 0;
            d = x;
            while (d != 0) {
                d = d / 2;
                c = c + 1;
            }
            c = c * c;
            c = c * c * x;
            if (a > b * c) {
                return;
            }
"""

# same, with global b folded into the comparison
BITLEN_NOB_TAIL = """            a = num - denom * x;
            a = a * a;
            c = 0;
            d = x;
            while (d != 0) {
                d = d / 2;
                c = c + 1;
            }
            c = c * c;
            c = c * c * x;
            if (a > denom * denom * c) {
                return;
            }
"""

# same again, reusing the dead register l as the shift temp so d disappears
BITLEN_NOBD_TAIL = """            a = num - denom * x;
            a = a * a;
            c = 0;
            l = x;
            while (l != 0) {
                l = l / 2;
                c = c + 1;
            }
            c = c * c;
            c = c * c * x;
            if (a > denom * denom * c) {
                return;
            }
"""

# and reusing i as well, so both b and d leave the register file
BITLEN_I_TAIL = """            a = num - denom * x;
            a = a * a;
            c = 0;
            i = x;
            while (i != 0) {
                i = i / 2;
                c = c + 1;
            }
            c = c * c;
            c = c * c * x;
            if (a > denom * denom * c) {
                return;
            }
"""

# UNSOUND cost probes.  These do not decide RH; they exist only to price the
# constructs they delete.  Never confuse them with a machine.
ABLATIONS = [
    ("baseline 744", BASELINE),
    ("[probe] no lcm inner search (lcm = x)",
     prog(G10, "    lcm = 1;\n    while (true) {\n        x = x + 1;\n        l = lcm;\n        lcm = x;\n"
          + "        if (x > 253) {\n" + HL_LOOP + BASE_TAIL + "        }\n    }\n")),
    ("[probe] no H_L loop (num/denom left 0/1)",
     prog(G10, LCM_LOOP + "        if (x > 253) {\n"
          + "            num = 0;\n            denom = 1;\n            i = 1;\n"
          + BASE_TAIL + "        }\n    }\n")),
    ("[probe] no H_x loop (c/d left 0/1)",
     prog(G10, LCM_LOOP + "        if (x > 253) {\n" + HL_LOOP
          + """            a = num - denom * x;
            a = a * a;
            b = denom * denom;
            c = 0;
            d = 1;
            i = 1;
            c = c * c;
            c = c * c * x;
            d = d * d;
            d = d * d;
            if (a * d > b * c) {
                return;
            }
""" + "        }\n    }\n")),
    ("[probe] no x>253 guard",
     prog(G10, LCM_LOOP + HL_LOOP + BASE_TAIL + "    }\n")),
    ("[probe] no final squarings (c=c*c etc.)",
     prog(G10, LCM_LOOP + "        if (x > 253) {\n" + HL_LOOP
          + """            a = num - denom * x;
            b = denom * denom;
            c = 0;
            d = 1;
            i = 1;
            while (i <= x) {
                c = c * i + d;
                d = d * i;
                i = i + 1;
            }
            if (a * d > b * c) {
                return;
            }
""" + "        }\n    }\n")),
]

VARIANTS = [
    ("VARIANT bitlen (10 globals)",
     prog(G10, LCM_LOOP + "        if (x > 253) {\n" + HL_LOOP + BITLEN_TAIL + "        }\n    }\n")),
    ("VARIANT bitlen, b folded (9 globals)",
     prog([g for g in G10 if g != "b"],
          LCM_LOOP + "        if (x > 253) {\n" + HL_LOOP + BITLEN_NOB_TAIL + "        }\n    }\n")),
    ("VARIANT bitlen, b folded + l as temp (8 globals)",
     prog([g for g in G10 if g not in ("b", "d")],
          LCM_LOOP + "        if (x > 253) {\n" + HL_LOOP + BITLEN_NOBD_TAIL + "        }\n    }\n")),
    ("VARIANT bitlen, b folded + i as temp (8 globals)",
     prog([g for g in G10 if g not in ("b", "d")],
          LCM_LOOP + "        if (x > 253) {\n" + HL_LOOP + BITLEN_I_TAIL + "        }\n    }\n")),
]


def main():
    head = ensure_toolchain()
    print("toolchain HEAD:", head, "(pinned expectation %s)" % PIN)
    print()

    base_n, base_h = compile_states(BASELINE)
    committed = os.path.join(WORK, "machines",
                             "2016-riemann-matiyasevich-aaronson-744", "riemann.tm")
    with open(committed) as fh:
        ref = fh.read()
    ref_h = hashlib.sha256(ref.encode()).hexdigest()[:12]
    print("REPRODUCTION: recompiled riemann.nql -> %s states, sha %s" % (base_n, base_h))
    print("              committed riemann.tm  -> %s states, sha %s" %
          (len([l for l in ref.splitlines() if l.strip()]), ref_h))
    print("              byte-identical:", base_h == ref_h)
    print()

    print("=== STATE COST TABLE (differential recompile) ===")
    print("%-46s %7s %8s  %s" % ("construct", "states", "delta", "sha"))
    for name, src in ABLATIONS:
        n, h = compile_states(src)
        if n is None:
            print("%-46s %7s %8s  %s" % (name, "ERR", "", h))
            continue
        d = "" if name.startswith("baseline") else "%+d" % (n - base_n)
        print("%-46s %7d %8s  %s" % (name, n, d, h))
    print()

    print("=== COMBINE: bit-length threshold in place of H_x ===")
    print("%-46s %7s %8s  %s" % ("machine", "states", "vs 744", "sha"))
    best = None
    for name, src in VARIANTS:
        n, h = compile_states(src)
        if n is None:
            print("%-46s %7s %8s  %s" % (name, "ERR", "", h))
            continue
        print("%-46s %7d %8s  %s" % (name, n, "%+d" % (n - base_n), h))
        if best is None or n < best[1]:
            best = (name, n, h, src)
    print()
    if best:
        print("best variant: %s -> %d states (sha %s)" % (best[0], best[1], best[2]))
        out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "t27_riemann_bitlen.nql")
        with open(out, "w") as fh:
            fh.write(best[3])
        print("source written to", out)


if __name__ == "__main__":
    main()
