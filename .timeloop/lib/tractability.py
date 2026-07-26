"""Score how attackable a formal statement is, from its STRUCTURE not its length.

Replaces the length proxy, which was proved bad at T12 (`BB_1`, `τ_two`,
`P_subset_NP` are all short and hard) and then used anyway at T15, where it drew
`W 3 15 = 218` — thirty characters, SAT-scale.

The signals are read off the statement's logical shape:

  ∃ over a finite/concrete type   → a witness hunt. Exhibit the object and check.
  ∀ over an infinite type          → needs an argument, not a search.
  sInf / sSup                      → TWO obligations: a witness AND a minimality
                                     proof over everything smaller. Usually the
                                     minimality half is the killer.
  asymptotics (=O, Tendsto, atTop) → analysis; no finite certificate exists.
  f <literal> = <literal>          → may unfold definitionally; cheapest case.

Higher score = more attackable. Negative = do not bother.

Calibrated against outcomes this arena actually observed on 2026-07-25, not
against intuition — see the `tractability` item in the blind exam.
"""

import re

# (regex, weight, why) — weights are ordinal, not a probability of anything
SIGNALS = [
    # ── strongly negative: no finite certificate ────────────────────────────
    (r"\bsInf\b|\bsSup\b", -6,
     "sInf/sSup: needs a witness AND minimality over all smaller candidates"),
    (r"=O\[|=Θ\[|IsLittleO|Tendsto|atTop|𝓝", -6,
     "asymptotic/limit statement: no finite certificate"),
    (r"\bSet\.Infinite\b|\bInfinite\b", -4,
     "infinitude claim"),
    (r"answer\(sorry\)", -5,
     "the statement itself is an unfilled placeholder"),
    # ── negative: unbounded quantification ──────────────────────────────────
    (r"∀\s*\(?\s*\w+\s*:\s*ℕ\b(?![^,]*≤)", -3,
     "∀ over ℕ with no bound"),
    (r"∀\s*\(?\s*\w+\s*:\s*(ℝ|ℚ|ℤ)\b", -3,
     "∀ over an infinite ordered field/ring"),
    (r"\bPrime\b.*∀|∀.*\bPrime\b", -2,
     "universally quantified primality"),
    # ── positive: finite, checkable ─────────────────────────────────────────
    (r"\bFin\s+\d+\b", +2, "concrete Fin n: finite type"),
    (r"\bFinset\b|\bIcc\b|\bFintype\b", +1, "finite container"),
    (r"∃", +2, "existential: a witness may suffice"),
    (r"\bDecidable\b|\bDecidableEq\b|\bDecidableRel\b", +1, "decidability available"),
    # ── strongly positive: literal evaluation ───────────────────────────────
    (r"^\s*[\w.]+\s*:\s*\w+\s+\d+(\s+\d+)*\s*=\s*\d+\s*$", +5,
     "f <literals> = <literal>: may unfold definitionally"),
]


def _resolve(stmt: str, file_text: str, depth: int = 2) -> str:
    """Splice in the bodies of definitions the statement mentions.

    THIS is the whole point, and it was found by validation, not design:
    `a 1 = 1` and `W 3 15 = 218` are syntactically identical — `f <literals> =
    <literal>` — yet one falls to `rfl` and the other is SAT-scale. The signal
    is not in the statement. It is in what the definition bottoms out in:
    `a` is computable; `W` unfolds to `sInf { N | ∀ colouring ... }`.

    A scorer that reads only the statement therefore cannot work, and the first
    version of this file did exactly that and scored both 0.
    """
    seen, text = set(), stmt
    for _ in range(depth):
        idents = set(re.findall(r"\b([A-Za-z][\w']*)\b", text)) - seen
        added = ""
        for ident in idents:
            m = re.search(
                r"^\s*(?:noncomputable\s+)?(?:private\s+)?def\s+" + re.escape(ident)
                + r"\b(.*?)(?=\n\s*(?:@\[|def |theorem |lemma |end )|\Z)",
                file_text, re.DOTALL | re.MULTILINE)
            if m:
                added += "\n" + m.group(1)
                seen.add(ident)
        if not added:
            break
        text += added
    return text


def score(stmt: str, file_text: str | None = None) -> tuple[int, list[str]]:
    """Return (score, reasons). Resolves definitions when file_text is given."""
    if file_text:
        stmt = _resolve(stmt, file_text)
    # keep just the proposition: drop the attribute and the binder name
    s = re.sub(r"@\[[^\]]*\]", "", stmt)
    s = re.sub(r"^\s*(theorem|lemma)\s+[\w.]+\s*", "", s.strip())
    total, why = 0, []
    for pat, w, reason in SIGNALS:
        if re.search(pat, s, re.MULTILINE):
            total += w
            why.append(f"{w:+d} {reason}")
    if not why:
        why.append("+0 no signal matched")
    return total, why


def verdict(n: int) -> str:
    if n >= 4:
        return "attempt"
    if n >= 0:
        return "maybe"
    return "skip"
