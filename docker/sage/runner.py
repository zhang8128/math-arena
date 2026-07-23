import json
import sys

from sage.all import QQ, ZZ, PolynomialRing, factor


def _predicate(predicate_id: str, n: object) -> tuple[bool, int]:
    integer = ZZ(n)
    if predicate_id == "euler_prime":
        value = integer**2 + integer + 41
        return bool(value.is_prime()), int(value)
    if predicate_id == "fermat_prime":
        value = ZZ(2) ** (ZZ(2) ** integer) + 1
        return bool(value.is_prime()), int(value)
    if predicate_id == "sum_odds":
        value = integer**2
        evaluated = sum(ZZ(2 * index + 1) for index in range(int(integer)))
        return bool(evaluated == value), int(value)
    if predicate_id == "quadratic_two_prime":
        value = integer**2 + integer + 2
        return bool(value.is_prime()), int(value)
    if predicate_id == "quadratic_three_prime":
        value = integer**2 + integer + 3
        return bool(value.is_prime()), int(value)
    if predicate_id == "sum_integers":
        value = integer * (integer + 1) // 2
        evaluated = sum(ZZ(index) for index in range(1, int(integer) + 1))
        return bool(evaluated == value), int(value)
    raise ValueError(f"unsupported predicate: {predicate_id}")


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
    elif operation == "verify_sum_integers_induction":
        ring = PolynomialRing(QQ, "n")
        n = ring.gen()
        base = ZZ(0)
        step = (n + 1) * (n + 2) / 2 - n * (n + 1) / 2 - (n + 1)
        response = {"ok": True, "base": base == 0, "step": step == 0}
    elif operation == "find_integer_counterexample":
        start = ZZ(request["start"])
        stop = ZZ(request["stop"])
        order = request["order"]
        values = range(int(start), int(stop))
        if order == "boundary_first":
            values = range(int(stop) - 1, int(start) - 1, -1)
        elif order != "ascending":
            raise ValueError(f"unsupported search order: {order}")
        response = {"ok": True, "found": False}
        for candidate in values:
            holds, value = _predicate(request["predicate_id"], candidate)
            if not holds:
                response = {
                    "ok": True,
                    "found": True,
                    "n": candidate,
                    "value": value,
                }
                break
    else:
        response = {"ok": False, "error": f"unsupported operation: {operation}"}
    json.dump(response, sys.stdout, sort_keys=True)


if __name__ == "__main__":
    main()
