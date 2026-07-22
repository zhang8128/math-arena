import json
from pathlib import Path

import pytest

from mathloop.sources.jsonl import JsonlProblemSource


def _record() -> dict[str, object]:
    return {
        "source_id": "demo/one",
        "source_uri": "https://example.test/one",
        "statement": "All values are prime",
        "normalized_statement": "forall n, P(n)",
        "domain": "number_theory",
        "features": {"finite_witness": True},
        "checker": {"kind": "integer_predicate", "predicate_id": "euler_prime"},
    }


def test_changed_statement_creates_new_source_hash(tmp_path: Path) -> None:
    source = tmp_path / "problems.jsonl"
    record = _record()
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
    record = _record()
    first_path.write_text(json.dumps(record) + "\n")
    second_path.write_text(json.dumps(dict(reversed(record.items()))) + "\n")

    first = next(JsonlProblemSource(first_path).read())
    second = next(JsonlProblemSource(second_path).read())

    assert first.source_hash == second.source_hash


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_json_numbers_are_rejected_with_source_context(
    tmp_path: Path, constant: str
) -> None:
    source = tmp_path / "problems.jsonl"
    source.write_text(
        json.dumps(_record()).replace('"finite_witness": true', f'"score": {constant}') + "\n"
    )

    with pytest.raises(ValueError) as error:
        next(JsonlProblemSource(source).read())

    assert f"{source}:1:" in str(error.value)
    assert "non-finite JSON number" in str(error.value)


def test_malformed_json_reports_source_path_and_line_number(tmp_path: Path) -> None:
    source = tmp_path / "problems.jsonl"
    source.write_text("\n{not valid json}\n")

    with pytest.raises(ValueError) as error:
        next(JsonlProblemSource(source).read())

    assert f"{source}:2: invalid JSON" in str(error.value)


def test_schema_invalid_json_reports_source_path_and_line_number(tmp_path: Path) -> None:
    source = tmp_path / "problems.jsonl"
    record = _record()
    del record["source_id"]
    source.write_text("\n" + json.dumps(record) + "\n")

    with pytest.raises(ValueError) as error:
        next(JsonlProblemSource(source).read())

    message = str(error.value)
    assert f"{source}:2: invalid problem record" in message
    assert "source_id" in message
