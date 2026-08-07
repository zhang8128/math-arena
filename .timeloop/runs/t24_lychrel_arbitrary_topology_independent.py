#!/usr/bin/env python3
"""Standalone binary-CNF audit of the T24 n=0 obstruction."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


SOURCE = Path(__file__).with_name("t21_lychrel_multi_interface.json")


@dataclass(frozen=True)
class Atom:
    key: str | None
    value: int | None


class BinaryCNF:
    def __init__(self, base: int, phases: list[dict[str, object]]) -> None:
        self.base = base
        self.phases = phases
        self.width = math.ceil(math.log2(base))
        self.ids: dict[str, int] = {}
        self.clauses: list[list[int]] = []
        self.hard_clause_count = 0
        self.column_groups: list[tuple[str, int, int]] = []

    def variable(self, key: str) -> int:
        if key not in self.ids:
            self.ids[key] = len(self.ids) + 1
        return self.ids[key]

    def digit_bit(self, key: str, bit: int) -> int:
        return self.variable(f"digit:{key}:bit{bit}")

    def atom_bit(self, atom: Atom, bit: int) -> int | bool:
        if atom.key is not None:
            return self.digit_bit(atom.key, bit)
        assert atom.value is not None
        return bool((atom.value >> bit) & 1)

    def render(self, phase: int, n: int) -> list[Atom]:
        word = self.phases[phase]
        fragments = word["fragments"]
        repeats = word["repeats"]
        assert isinstance(fragments, list) and isinstance(repeats, list)
        rendered: list[Atom] = []
        for fragment_index, fragment in enumerate(fragments):
            assert isinstance(fragment, list)
            if fragment_index:
                repeat = repeats[fragment_index - 1]
                value = self.base - 1 if repeat == 16 else 0
                rendered.extend(Atom(None, value) for _ in range(n))
            rendered.extend(
                Atom(f"p{phase}:f{fragment_index}:d{offset}", None)
                for offset in range(len(fragment))
            )
        return rendered

    @staticmethod
    def _values(term: int | bool) -> tuple[bool, ...]:
        return (term,) if isinstance(term, bool) else (False, True)

    @staticmethod
    def _negated_condition(
        terms: tuple[int | bool, ...],
        values: tuple[bool, ...],
    ) -> list[int] | None:
        clause = []
        for term, value in zip(terms, values):
            if isinstance(term, bool):
                if term != value:
                    return None
            else:
                clause.append(-term if value else term)
        return clause

    def full_adder(
        self,
        prefix: str,
        bit: int,
        left: int | bool,
        right: int | bool,
        carry_in: int | bool,
    ) -> tuple[int, int]:
        total_bit = self.variable(f"aux:{prefix}:sum{bit}")
        carry_out = self.variable(f"aux:{prefix}:carry{bit}")
        terms = (left, right, carry_in)
        value_sets = tuple(self._values(term) for term in terms)
        for values in itertools.product(*value_sets):
            condition = self._negated_condition(terms, values)
            if condition is None:
                continue
            total = sum(values)
            self.clauses.append(
                condition + ([total_bit] if total % 2 else [-total_bit])
            )
            self.clauses.append(
                condition + ([carry_out] if total >= 2 else [-carry_out])
            )
        return total_bit, carry_out

    def add_binary_sum(
        self,
        prefix: str,
        left: Atom,
        right: Atom,
        low_carry: int | bool,
    ) -> list[int]:
        output = []
        carry: int | bool = low_carry
        for bit in range(self.width):
            total_bit, carry = self.full_adder(
                prefix,
                bit,
                self.atom_bit(left, bit),
                self.atom_bit(right, bit),
                carry,
            )
            output.append(total_bit)
        assert isinstance(carry, int)
        output.append(carry)
        return output

    def add_target_sum(
        self,
        prefix: str,
        target: Atom,
        base_carry: int | bool,
    ) -> list[int]:
        output = []
        carry: int | bool = False
        for bit in range(self.width):
            base_term: int | bool = (
                base_carry if (self.base >> bit) & 1 else False
            )
            total_bit, carry = self.full_adder(
                prefix,
                bit,
                self.atom_bit(target, bit),
                base_term,
                carry,
            )
            output.append(total_bit)
        assert isinstance(carry, int)
        output.append(carry)
        return output

    def equate(self, left: int, right: int) -> None:
        self.clauses.append([-left, right])
        self.clauses.append([left, -right])

    def build(self) -> None:
        digit_values: dict[str, int] = {}
        for phase, word in enumerate(self.phases):
            fragments = word["fragments"]
            assert isinstance(fragments, list)
            for fragment_index, fragment in enumerate(fragments):
                assert isinstance(fragment, list)
                for offset, reference_value in enumerate(fragment):
                    key = f"p{phase}:f{fragment_index}:d{offset}"
                    digit_values[key] = int(reference_value)
                    for bit in range(self.width):
                        self.digit_bit(key, bit)
                    for invalid in range(self.base, 1 << self.width):
                        self.clauses.append(
                            [
                                -self.digit_bit(key, bit)
                                if (invalid >> bit) & 1
                                else self.digit_bit(key, bit)
                                for bit in range(self.width)
                            ]
                        )
            leading = "p%d:f0:d0" % phase
            self.clauses.append(
                [self.digit_bit(leading, bit) for bit in range(self.width)]
            )

        self.hard_clause_count = len(self.clauses)

        for phase in range(len(self.phases)):
            source = self.render(phase, 0)
            next_phase = (phase + 1) % len(self.phases)
            output = self.render(next_phase, int(phase == len(self.phases) - 1))
            if len(output) not in (len(source), len(source) + 1):
                raise ValueError("saved topology has an invalid transition length")
            for column in range(len(output)):
                group_start = len(self.clauses)
                if column < len(source):
                    left = source[column]
                    right = source[-1 - column]
                else:
                    left = right = Atom(None, 0)
                target = output[-1 - column]
                arithmetic_carry_in: int | bool = (
                    self.variable(f"carry:p{phase}:col{column - 1}")
                    if column
                    else False
                )
                arithmetic_carry_out: int | bool = (
                    self.variable(f"carry:p{phase}:col{column}")
                    if column + 1 < len(output)
                    else False
                )
                lhs = self.add_binary_sum(
                    f"p{phase}:col{column}:lhs",
                    left,
                    right,
                    arithmetic_carry_in,
                )
                rhs = self.add_target_sum(
                    f"p{phase}:col{column}:rhs",
                    target,
                    arithmetic_carry_out,
                )
                for lhs_bit, rhs_bit in zip(lhs, rhs):
                    self.equate(lhs_bit, rhs_bit)
                self.column_groups.append(
                    (
                        f"phase={phase},n=0,column={column}",
                        group_start,
                        len(self.clauses),
                    )
                )

        self.reference_digits = digit_values

    def selected_column_clauses(self, provenances: set[str]) -> list[list[int]]:
        available = {provenance for provenance, _, _ in self.column_groups}
        if not provenances <= available:
            raise ValueError("unknown binary column provenance")
        selected = self.clauses[: self.hard_clause_count]
        for provenance, start, stop in self.column_groups:
            if provenance in provenances:
                selected.extend(self.clauses[start:stop])
        return selected

    def reference_units(self) -> list[list[int]]:
        return [
            [
                self.digit_bit(key, bit)
                if (value >> bit) & 1
                else -self.digit_bit(key, bit)
            ]
            for key, value in self.reference_digits.items()
            for bit in range(self.width)
        ]

    def dimacs_digest_and_write(
        self,
        path: Path,
        extra_clauses: list[list[int]] | None = None,
    ) -> str:
        clauses = self.clauses + ([] if extra_clauses is None else extra_clauses)
        digest = hashlib.sha256()
        with path.open("wb") as output:
            header = f"p cnf {len(self.ids)} {len(clauses)}\n".encode("ascii")
            output.write(header)
            digest.update(header)
            for clause in clauses:
                line = (" ".join(map(str, clause)) + " 0\n").encode("ascii")
                output.write(line)
                digest.update(line)
        return digest.hexdigest()


def solve_cadical(path: Path) -> str:
    completed = subprocess.run(
        ["cadical", "--quiet", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 20 and "s UNSATISFIABLE" in completed.stdout:
        return "unsatisfiable"
    if completed.returncode == 10 and "s SATISFIABLE" in completed.stdout:
        return "satisfiable"
    raise RuntimeError(
        f"CaDiCaL returned {completed.returncode}: "
        f"{completed.stdout[-200:]} {completed.stderr[-200:]}"
    )


def load_phases() -> list[dict[str, object]]:
    payload = json.loads(SOURCE.read_text())
    phases = payload["positive_control"]["phases"]
    if not isinstance(phases, list) or len(phases) != 6:
        raise ValueError("T21 JSON does not contain the six-phase control")
    return phases


def build_audit() -> dict[str, object]:
    phases = load_phases()
    version = subprocess.run(
        ["cadical", "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        calibration_formula = BinaryCNF(17, phases)
        calibration_formula.build()
        calibration_path = temporary / "base17.cnf"
        calibration_digest = calibration_formula.dimacs_digest_and_write(
            calibration_path,
            calibration_formula.reference_units(),
        )
        calibration_status = solve_cadical(calibration_path)
        if calibration_status != "satisfiable":
            raise AssertionError("binary encoding rejects the fixed base-17 control")

        results = []
        for base in range(18, 41):
            formula = BinaryCNF(base, phases)
            formula.build()
            path = temporary / f"base{base}.cnf"
            digest = formula.dimacs_digest_and_write(path)
            status = solve_cadical(path)
            results.append(
                {
                    "base": base,
                    "parameters_checked": 0,
                    "status": status,
                    "variable_count": len(formula.ids),
                    "clause_count": len(formula.clauses),
                    "dimacs_digest": digest,
                }
            )

    covered = [
        item["base"] for item in results if item["status"] == "unsatisfiable"
    ]
    return {
        "kind": "independent_binary_topology_audit",
        "implementation": "standalone binary digit encoding",
        "source": {
            "file": SOURCE.name,
            "sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        },
        "solver": {"engine": "CaDiCaL", "version": version},
        "calibration": {
            "base": 17,
            "fixed_digit_bits": 497 * calibration_formula.width,
            "status": calibration_status,
            "dimacs_digest": calibration_digest,
        },
        "bases_tested": len(results),
        "covered_bases": covered,
        "all_unsatisfiable": covered == list(range(18, 41)),
        "results": results,
    }


def main() -> None:
    print(json.dumps(build_audit(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
