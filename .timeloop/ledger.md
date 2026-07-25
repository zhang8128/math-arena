# Time Loop Ledger

Append-only. One line per turn. Newest at the bottom.

Format: `T<n> | <slug> | <outcome> | <what changed for the next turn>`

---

T0 | rabinowitsch-families | exhausted | Principal family `n^2+n+q` closed permanently: full prime runs ⟺ Heegner discriminants, largest is −163 (Rabinowitsch 1913 + Baker–Heegner–Stark). Do not re-search. Structure recorded: prime-run length is a class-number statement, so compute the discriminant before extending any prime-density search. Next: non-principal / non-maximal orders.

T1 | rabinowitsch-families | broke a conjecture | Naive extension "long run ⟹ h(D)=1" is FALSE: 6n²+6n+31 has D=−708, h=4, run 58. Real mechanism is TWO routes to avoiding small primes — inertness (D non-residue mod p) and coefficient absorption (p | gcd(a,b) ⟹ f(n) ≡ c mod p always). Derived law: run ≤ s(p−1), s=2 if a|b, p = first non-absorbed prime. Rabinowitsch falls out as the a=1 corollary. Next suggested: constructive search maximising p.

T2 | rabinowitsch-t2 | refuted T1's own next-action | Constructive search FAILS. Forms with first-bad-prime 89 have actual runs of 8. Reason: a SECOND constraint T1 missed — value growth (~a·n²) kills prime density faster than absorption buys headroom. Crossover at a≈7. Euler polynomial is optimal because a=1 minimises values AND h=1 maximises the bound, with no room to trade. DO NOT re-attempt constructive absorption for quadratics — closed. Next: test whether the tension appears for cubics.

T3 | forge-digit-dynamics | SETTLED + law derived | Complete cycle structure for 42 (b,d) pairs — exhaustive below a provable bound, so these are theorems not searches. Then derived an exact law for d=2 fixed points: completing the square on `a(b−a)=c(c−1)` gives `u²+v² = b²+1`, so fixed points ARE the sum-of-two-squares representations of b²+1, filtered by digit range. Validated b=2..120, exact set equality, zero mismatches. Counts are driven by primes ≡1 mod 4 dividing b²+1. Note b=110: representation exists but falls outside digit range — arithmetic supplies candidates, ranges filter them.

T4 | forge-digit-dynamics | refuted T3's next-action, proved a family | No d=3 analogue of the d=2 law: the condition `a(b−a²)=c(c²−1)` is a cubic, not a conic, and counts track no factorisation invariant of b³±1. DO NOT look for one. But proved a constructive family: for d≥3, base b=k^(d−1) has fixed points k^d and k^d+1, because k·b=k^d collapses the condition to m^d=m. The side condition k<k^(d−1) is exactly why d=2 has no such family. Verified d∈{3,4,5}, k≤6. Next: b=16,d=3 has 24 fixed points — check whether the excess is 3-digit.
