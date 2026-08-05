from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from lychrel_templates import connector_search, reachable_connectors, search_lines


def test_base26_exterior_matches_published_reference_output() -> None:
    assert search_lines(26, 2, 2, 9, "Exterior") == [
        "T:10:10 1N5ELA6C   0D59ME5N",
        "T:10:10 1N5ELA6CP 00D59ME5N",
    ]


def test_base26_interior_matches_published_reference_output() -> None:
    assert search_lines(26, 2, 2, 3, "Interior") == [
        "F:01:01  0J BI ",
        "F:01:01 00J BIP",
        "T:10:10  P6 E7 ",
        "T:10:10 PP6 E70",
    ]


def test_reachability_recovers_published_base11_and_base26_connectors() -> None:
    base26 = set(reachable_connectors(26, 2, 2, 9, "Exterior")) & set(
        reachable_connectors(26, 2, 2, 3, "Interior")
    )
    base11 = set(reachable_connectors(11, 3, 3, 8, "Exterior")) & set(
        reachable_connectors(11, 3, 3, 22, "Interior")
    )
    assert base26 == {(True, (1, 0), (1, 0))}
    assert base11 == {(True, (1, 0, 0), (1, 0, 0))}


def test_connector_report_distinguishes_exhaustion_from_depth_cutoff() -> None:
    shallow = connector_search(26, 2, 2, 1, "Exterior")
    complete = connector_search(26, 2, 2, 100, "Exterior")
    assert shallow["exhausted"] is False
    assert complete["exhausted"] is True
    assert complete["reached_depth"] >= 8
