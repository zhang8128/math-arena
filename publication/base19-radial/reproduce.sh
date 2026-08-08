#!/usr/bin/env bash
set -euo pipefail

mode="${1:-quick}"
case "$mode" in
  quick|full) ;;
  *)
    echo "usage: $0 [quick|full]" >&2
    exit 2
    ;;
esac

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
repo_root="$(CDPATH= cd -- "$script_dir/../.." && pwd -P)"
task_tmp="$(mktemp -d "${TMPDIR:-/tmp}/base19-radial-reproduce.XXXXXX")"

cleanup() {
  rm -rf -- "$task_tmp"
}
trap cleanup EXIT HUP INT TERM

for tool in uv lean lake shasum cmp git grep; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "required tool is unavailable: $tool" >&2
    exit 1
  fi
done

check_exact() {
  label="$1"
  expected="$2"
  actual="$3"
  if [ "$actual" != "$expected" ]; then
    echo "$label version mismatch: expected '$expected', got '$actual'" >&2
    exit 1
  fi
}

check_exact "uv" "uv 0.8.3 (7e78f54e7 2025-07-24)" "$(uv --version)"
check_exact "Python" "Python 3.13.5" "$(uv run --frozen python --version)"
check_exact "Z3" "5.0.0" "$(uv run --frozen --extra exact python -c 'import z3; print(z3.get_version_string())')"
case "$(lean --version)" in
  "Lean (version 4.32.2,"*) ;;
  *) echo "Lean version mismatch; expected 4.32.2" >&2; exit 1 ;;
esac
case "$(lake --version)" in
  "Lake version 5.0.0-src+f3b06c7 (Lean version 4.32.2)") ;;
  *) echo "Lake version mismatch; expected 5.0.0-src+f3b06c7" >&2; exit 1 ;;
esac

cd "$script_dir"
shasum -a 256 -c SHA256SUMS
cd "$repo_root"

python_run=(uv run --frozen --extra exact python)
pytest_run=(uv run --frozen --extra exact --extra dev pytest)

"${python_run[@]}" publication/base19-radial/scripts/build_manifest.py \
  publication/base19-radial/instance/topology.json \
  "$task_tmp/equations.json"
cmp publication/base19-radial/instance/equations.json "$task_tmp/equations.json"

"${python_run[@]}" publication/base19-radial/scripts/render_lean_instance.py \
  publication/base19-radial/instance/equations.json \
  "$task_tmp/InstanceData.lean"
cmp publication/base19-radial/lean/Base19Radial/Generated/InstanceData.lean \
  "$task_tmp/InstanceData.lean"

"${python_run[@]}" publication/base19-radial/scripts/render_lean_data.py \
  --frontier publication/base19-radial/certificates/frontier.json \
  --witness publication/base19-radial/certificates/delete-p0-c0.json \
  --output-dir "$task_tmp/generated"
for generated in FrontierData.lean WitnessData.lean Witness.lean; do
  cmp "publication/base19-radial/lean/Base19Radial/Generated/$generated" \
    "$task_tmp/generated/$generated"
done

for frontier in frontier.json minimal-core-frontier.json; do
  "${python_run[@]}" publication/base19-radial/scripts/verify_frontier.py \
    publication/base19-radial/instance/equations.json \
    "publication/base19-radial/certificates/$frontier"
done

"${python_run[@]}" publication/base19-radial/scripts/audit_deletions.py \
  --workers 1 \
  --output publication/base19-radial/certificates/deletions.jsonl

"${pytest_run[@]}" publication/base19-radial/tests/test_publication_artifact.py -q

(
  cd publication/base19-radial/lean
  lake clean
  lake build
  lake exe export_manifest > "$task_tmp/lean-equations.json"
  grep -F '#print axioms' Base19Radial/RadialTests.lean >/dev/null
  grep -F '#print axioms' Base19Radial/Generated/Witness.lean >/dev/null
  lake env lean Base19Radial/RadialTests.lean | tee "$task_tmp/radial-axioms.txt"
  lake env lean Base19Radial/Generated/Witness.lean | tee "$task_tmp/witness-axioms.txt"
)
"${python_run[@]}" publication/base19-radial/scripts/compare_manifests.py \
  publication/base19-radial/instance/equations.json \
  "$task_tmp/lean-equations.json"
grep -F "'Base19Radial.radialTinyProblemUnsat' depends on axioms: [propext]" \
  "$task_tmp/radial-axioms.txt" >/dev/null
grep -F "'Base19Radial.deleteP0C0Sat' depends on axioms: [propext]" \
  "$task_tmp/witness-axioms.txt" >/dev/null

if [ "$mode" = "full" ]; then
  workers="${BASE19_WORKERS:-6}"
  "${python_run[@]}" publication/base19-radial/scripts/audit_deletions.py \
    --workers "$workers" \
    --output "$task_tmp/deletions.jsonl"
  cmp publication/base19-radial/certificates/deletions.jsonl \
    "$task_tmp/deletions.jsonl"

  "${python_run[@]}" publication/base19-radial/scripts/export_certificates.py \
    --frontier "$task_tmp/frontier.json" \
    --witness "$task_tmp/delete-p0-c0.json" \
    --minimal-core-frontier "$task_tmp/minimal-core-frontier.json"
  for certificate in frontier.json delete-p0-c0.json minimal-core-frontier.json; do
    cmp "publication/base19-radial/certificates/$certificate" \
      "$task_tmp/$certificate"
  done
fi

echo "base19 radial artifact reproduction ($mode) passed"
