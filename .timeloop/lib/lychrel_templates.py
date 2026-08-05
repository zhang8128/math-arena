"""Literal Python port of the public-domain reverse-add carry search.

The tuple layouts and traversal order follow search.hs.  This is research
instrumentation, not a replacement for independent arithmetic verification.
"""

from functools import lru_cache
from itertools import product


def inv_carry(carries):
    return tuple(1 - c for c in carries)


def inv_digit(base, digit):
    return base - 1 - digit


@lru_cache(maxsize=None)
def gen_carries(length):
    # Haskell convIntToCs enumerates the low-order bit first.
    return tuple(
        tuple((number // (2 ** i)) % 2 for i in range(length))
        for number in range(2 ** length)
    )


def add_digitwise(base, left, right, carry):
    total = left + right + carry
    return total % base, total // base


def add_digit_pair(base, digits, carries):
    left, left_carry = add_digitwise(base, digits[0], digits[1], carries[0])
    right, right_carry = add_digitwise(base, digits[0], digits[1], carries[1])
    return (left, right), (left_carry, right_carry)


@lru_cache(maxsize=None)
def calc_digit_pair(base, dla, dra, clr, crr):
    digits = (dla, dra)
    left_carries = []
    right_carries = []
    for carry_pair in zip(clr, crr):
        digits, output_carries = add_digit_pair(base, digits, carry_pair)
        left_carries.append(output_carries[0])
        right_carries.append(output_carries[1])
    return digits[0], digits[1], tuple(left_carries), tuple(right_carries)


@lru_cache(maxsize=None)
def calc_middle(base, digit, right_carries):
    left_carries = []
    for carry in right_carries:
        digit, left_carry = add_digitwise(base, digit, digit, carry)
        left_carries.append(left_carry)
    return digit, tuple(left_carries)


def calc_conn(base, adl, acl, bcl):
    # Keep the reference program's calculation exactly, including its use of
    # acl/acr in both folds.  bcl is part of the checked connector state.
    del bcl
    acr = inv_carry(acl)
    digits = (adl, inv_digit(base, adl))
    for carries in zip(acl, acr):
        digits, _ = add_digit_pair(base, digits, carries)
    mdl, bdl = digits[0], digits[0]
    digits = (bdl, inv_digit(base, bdl))
    for carries in zip(acl, acr):
        digits, _ = add_digit_pair(base, digits, carries)
    return mdl, digits[0]


def check_conn(base, adl, mdl, acl, acr, bcl, bcr):
    mdl_prime, adl_prime = calc_conn(base, adl, acl, bcl)
    if (
        adl in (0, base - 1)
        and adl == adl_prime
        and mdl == mdl_prime
        and acl == inv_carry(acr)
        and bcl == inv_carry(bcr)
    ):
        return adl != 0, acl, bcl
    return None


@lru_cache(maxsize=None)
def _calc_half(base, side, half_input):
    # Input tuple is (dla, dra, fixed-left, fixed-right).  On Exterior the
    # left carry list is fixed and the incoming right list is fixed; Interior
    # fixes the incoming left and outgoing right lists.
    dla, dra, fixed_left, fixed_right = half_input
    carry_length = len(fixed_left)
    results = []
    for candidate in gen_carries(carry_length):
        if side == "Exterior":
            dlb, drb, cll, crl = calc_digit_pair(
                base, dla, dra, candidate, fixed_right
            )
            if cll == fixed_left:
                results.append(((dla, dra, fixed_left, fixed_right), (
                    dlb,
                    drb,
                    candidate,
                    crl,
                )))
        else:
            dlb, drb, cll, crl = calc_digit_pair(
                base, dla, dra, fixed_left, candidate
            )
            if crl == fixed_right:
                results.append(((dla, dra, fixed_left, fixed_right), (
                    dlb,
                    drb,
                    cll,
                    candidate,
                )))
    return tuple(results)


def calc_half(base, side, half_input):
    return iter(_calc_half(base, side, half_input))


@lru_cache(maxsize=None)
def calc_vertical(base, side, state):
    results = []
    if side == "Exterior":
        adla, bdla, acll, acrr, bcll, bcrr = state
        a_inputs = ((adla, adra, acll, acrr) for adra in range(base))
    else:
        adra, adlb_fixed, aclr, acrl, bclr, bcrl = state
        a_inputs = ((adla, adra, aclr, acrl) for adla in range(base))

    for a_input in a_inputs:
        for _, a_output in calc_half(base, side, a_input):
            if side == "Exterior":
                b_inputs = ((bdla, a_output[1], bcll, bcrr),)
            else:
                b_inputs = (
                    (bdla, a_output[1], bclr, bcrl) for bdla in range(base)
                )
            for b_input in b_inputs:
                for _, b_output in calc_half(base, side, b_input):
                    if side == "Exterior":
                        if a_input[1] != b_output[1]:
                            continue
                        next_state = (
                            b_output[0],
                            a_output[0],
                            a_output[2],
                            a_output[3],
                            b_output[2],
                            b_output[3],
                        )
                        adl, mdl = b_output[0], a_output[0]
                    else:
                        if (
                            a_input[0] != b_output[0]
                            or adlb_fixed != a_output[0]
                        ):
                            continue
                        next_state = (
                            b_output[1],
                            b_input[0],
                            a_output[2],
                            a_output[3],
                            b_output[2],
                            b_output[3],
                        )
                        adl = inv_digit(base, b_output[1])
                        mdl = b_input[0]
                    conn = check_conn(
                        base,
                        adl,
                        mdl,
                        a_output[2],
                        a_output[3],
                        b_output[2],
                        b_output[3],
                    )
                    results.append((next_state, (a_input[0], a_input[1]), conn))
    return tuple(results)


def gen_heads(base, pa, pb, side):
    if side == "Exterior":
        acll = (0,) * (pa - 1) + (1,)
        acrr = (0,) * pa
        bcll = (0,) * (pb - 1) + (1,)
        bcrr = (0,) * pb
        yield (1, 1, acll, acrr, bcll, bcrr)
        return
    for digit in range(base):
        for ac in gen_carries(pa):
            for bc in gen_carries(pb):
                adra, bclr = calc_middle(base, digit, bc)
                yield (adra, digit, ac, ac, bclr, bc)


def flatten(base, side, state, depth, digit_pairs=()):
    if depth == 0:
        return
    for next_state, digit_pair, conn in calc_vertical(base, side, state):
        path = digit_pairs + (digit_pair,)
        if conn is not None:
            yield path, conn
        yield from flatten(base, side, next_state, depth - 1, path)


def connector_search(base, pa, pb, max_depth, side):
    """Search unique carry states and report whether the graph was exhausted.

    State deduplication is sound for connector existence because future
    transitions depend only on the six fields in the reference search state.
    """
    if side not in ("Exterior", "Interior"):
        raise ValueError("side must be Exterior or Interior")
    frontier = [(head, ()) for head in gen_heads(base, pa, pb, side)]
    seen = {head for head, _ in frontier}
    found = {}
    reached_depth = 0
    for depth in range(1, max_depth + 1):
        reached_depth = depth
        next_frontier = []
        for state, path in frontier:
            for next_state, digit_pair, conn in calc_vertical(base, side, state):
                next_path = path + (digit_pair,)
                if conn is not None and conn not in found:
                    found[conn] = (depth, next_path)
                if next_state not in seen:
                    seen.add(next_state)
                    next_frontier.append((next_state, next_path))
        frontier = next_frontier
        if not frontier:
            break
    return {
        "connectors": found,
        "exhausted": not frontier,
        "reached_depth": reached_depth,
        "states": len(seen),
    }


def reachable_connectors(base, pa, pb, max_depth, side):
    """Return one shortest witness path for every reachable connector."""
    return connector_search(base, pa, pb, max_depth, side)["connectors"]


def show_digit(digit):
    if digit < 0 or digit >= 62:
        return "@"
    if digit < 10:
        return chr(digit + 48)
    if digit < 36:
        return chr(digit + 55)
    return chr(digit + 61)


def show_conn(conn):
    nonzero, acl, _bcl = conn
    carries = "".join(str(c) for c in acl)
    return ("T" if nonzero else "F") + ":" + carries + ":" + carries


def show_num_part(side, length, digit_pairs):
    if side == "Interior":
        value = " "
        for left, right in digit_pairs:
            value = show_digit(left) + value + show_digit(right)
        space = " " * (length - len(digit_pairs))
        return space + value + space
    left_value = "".join(show_digit(pair[0]) for pair in digit_pairs)
    right_value = "".join(show_digit(pair[1]) for pair in reversed(digit_pairs))
    space = " " * (2 * (length - len(digit_pairs)) + 1)
    return left_value + space + right_value


def search_lines(base, pa, pb, depth, side):
    if side not in ("Exterior", "Interior"):
        raise ValueError("side must be Exterior or Interior")
    lines = []
    for head in gen_heads(base, pa, pb, side):
        for digit_pairs, conn in flatten(base, side, head, depth):
            lines.append(
                show_conn(conn) + " " + show_num_part(side, depth, digit_pairs)
            )
    return lines
