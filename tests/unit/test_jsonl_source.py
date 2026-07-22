import json
from pathlib import Path

from mathloop.sources.jsonl import JsonlProblemSource


def test_changed_statement_creates_new_source_hash(tmp_path: Path) -> None:
    source = tmp_path / "problems.jsonl"
    record = {
        "source_id": "demo/one",
        "source_uri": "https://example.test/one",
        "statement": "All values are prime",
        "normalized_statement": "forall n, P(n)",
        "domain": "number_theory",
        "features": {"finite_witness": True},
        "checker": {"kind": "integer_predicate", "predicate_id": "euler_prime"},
    }
    source.write_text(json.dumps(record) + "\n")
    first = next(JsonlProblemSource(source).read())

    record["statement"] = "All nonnegative values are prime"
    source.write_text(json.dumps(record) + "\n")
    second = next(JsonlProblemSource(source).read())

    assert first.source_hash != second.source_hash
    assert first.source_id == second.source_id


def test_source_hash_uses_canonical_content_not_key_order_or_file_path(tmp_path: Path) -> None:
    first_path = tmp_path / "first.jsonl"
    second_path = tmp_path / "second.jsonl"
    record = {
        "source_id": "demo/one",
        "source_uri": "https://example.test/one",
        "statement": "All values are prime",
        "normalized_statement": "forall n, P(n)",
        "domain": "number_theory",
        "features": {"finite_witness": True},
        "checker": {"kind": "integer_predicate", "predicate_id": "euler_prime"},
    }
    first_path.write_text(json.dumps(record) + "\n")
    second_path.write_text(json.dumps(dict(reversed(record.items()))) + "\n")

    first = next(JsonlProblemSource(first_path).read())
    second = next(JsonlProblemSource(second_path).read())

    assert first.source_hash == second.source_hash
