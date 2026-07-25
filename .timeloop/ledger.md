# Time Loop Ledger

Append-only. One line per turn. Newest at the bottom.

Format: `T<n> | <slug> | <outcome> | <what changed for the next turn>`

---

T0 | rabinowitsch-families | exhausted | Principal family `n^2+n+q` closed permanently: full prime runs ⟺ Heegner discriminants, largest is −163 (Rabinowitsch 1913 + Baker–Heegner–Stark). Do not re-search. Structure recorded: prime-run length is a class-number statement, so compute the discriminant before extending any prime-density search. Next: non-principal / non-maximal orders.

T1 | rabinowitsch-families | broke a conjecture | Naive extension "long run ⟹ h(D)=1" is FALSE: 6n²+6n+31 has D=−708, h=4, run 58. Real mechanism is TWO routes to avoiding small primes — inertness (D non-residue mod p) and coefficient absorption (p | gcd(a,b) ⟹ f(n) ≡ c mod p always). Derived law: run ≤ s(p−1), s=2 if a|b, p = first non-absorbed prime. Rabinowitsch falls out as the a=1 corollary. Next suggested: constructive search maximising p.

T2 | rabinowitsch-t2 | refuted T1's own next-action | Constructive search FAILS. Forms with first-bad-prime 89 have actual runs of 8. Reason: a SECOND constraint T1 missed — value growth (~a·n²) kills prime density faster than absorption buys headroom. Crossover at a≈7. Euler polynomial is optimal because a=1 minimises values AND h=1 maximises the bound, with no room to trade. DO NOT re-attempt constructive absorption for quadratics — closed. Next: test whether the tension appears for cubics.
