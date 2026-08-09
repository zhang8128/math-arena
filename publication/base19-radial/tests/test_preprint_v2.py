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
