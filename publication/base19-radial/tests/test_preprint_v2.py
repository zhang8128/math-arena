import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARTIFACT = ROOT / "publication" / "base19-radial"
PREPRINT = ARTIFACT / "preprint-v2"


def test_bibliography_contains_every_required_primary_source() -> None:
    source = (PREPRINT / "references.bib").read_text(encoding="utf-8")
    for key in (
        "brownSeal",
        "oeisA060382",
        "Freuder1990",
        "DechterPearl1989",
        "deMouraUllrich2021",
        "CruzFilipeEtAl2017",
        "BaekCarneiroHeule2022",
        "cadical301",
        "z3Arithmetic",
        "leanBVDecide432",
    ):
        assert f"{{{key}," in source


def test_lean_bv_citation_discloses_native_evaluation_boundary() -> None:
    source = (PREPRINT / "citation-matrix.md").read_text(encoding="utf-8")
    match = re.search(r"^\|.*\| `leanBVDecide432` \|$", source, flags=re.MULTILINE)
    assert match is not None
    row = match.group(0)
    for required_fact in (
        "proved-sound LRAT checker",
        "`nativeEqTrue`",
        "packedMinimalCoreUnsat._native.bv_decide.ax_1_5",
        "f3b06c705e6c85f5314019d5d3baab0fec5b580c",
        "Std/Tactic/BVDecide/Reflect.lean",
        "Std/Tactic/BVDecide/LRAT/Checker.lean",
        "Lean/Meta/Tactic/BVDecide/Prover/Bitblast.lean",
    ):
        assert required_fact in row
    assert "soundness reduces to the verified checker" not in row
