import json
import sys

from sage.all import QQ, ZZ, PolynomialRing, factor


def main() -> None:
    request = json.load(sys.stdin)
    operation = request.get("operation")
    if operation == "factor":
        value = ZZ(request["value"])
        response = {"ok": True, "factors": [[int(p), int(e)] for p, e in factor(value)]}
    elif operation == "verify_sum_odds_induction":
        ring = PolynomialRing(QQ, "n")
        n = ring.gen()
        base = ZZ(0)
        step = (n + 1) ** 2 - n**2 - (2 * n + 1)
        response = {"ok": True, "base": base == 0, "step": step == 0}
    else:
        response = {"ok": False, "error": f"unsupported operation: {operation}"}
    json.dump(response, sys.stdout, sort_keys=True)


if __name__ == "__main__":
    main()
