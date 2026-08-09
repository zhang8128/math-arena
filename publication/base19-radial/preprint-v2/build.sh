#!/usr/bin/env bash
set -euo pipefail

export SOURCE_DATE_EPOCH=1786147200
export FORCE_SOURCE_DATE=1
export TZ=UTC

paper_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
cd "$paper_dir"

latexmk -C main.tex >/dev/null 2>&1 || true
latexmk -pdf -interaction=nonstopmode -halt-on-error -file-line-error main.tex

if grep -Eq 'undefined citations|undefined references|Citation.*undefined|Reference.*undefined' main.log; then
  echo "preprint build has undefined citations or references" >&2
  exit 1
fi
if grep -F 'Overfull \hbox' main.log >/dev/null; then
  echo "preprint build has an overfull box" >&2
  exit 1
fi
test -s main.pdf
