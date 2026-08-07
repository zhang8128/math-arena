#!/usr/bin/env python3
"""Compare two canonical equation manifests and locate the first mismatch."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def first_difference(left: Any, right: Any, path: str = "") -> str | None:
    if type(left) is not type(right):
        return path or "<root>"
    if isinstance(left, dict):
        left_keys = sorted(left)
        right_keys = sorted(right)
        if left_keys != right_keys:
            missing = sorted(set(left_keys) ^ set(right_keys))[0]
            return f"{path}.{missing}" if path else missing
        for key in left_keys:
            child = f"{path}.{key}" if path else key
            difference = first_difference(left[key], right[key], child)
            if difference is not None:
                return difference
        return None
    if isinstance(left, list):
        if len(left) != len(right):
            return f"{path}.length"
        for index, (left_item, right_item) in enumerate(zip(left, right, strict=True)):
            difference = first_difference(
                left_item,
                right_item,
                f"{path}[{index}]",
            )
            if difference is not None:
                return difference
        return None
    return None if left == right else (path or "<root>")


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    args = parser.parse_args(argv)
    left = _load(args.left)
    right = _load(args.right)
    difference = first_difference(left, right)
    if difference is not None:
        print(f"manifest mismatch at {difference}", file=sys.stderr)
        return 1
    if args.left.read_bytes() != args.right.read_bytes():
        print("manifests parse equally but canonical bytes differ", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
