# Turn $turn_id — $kind

$kind_rules

## Target

$target_block

## Recent ledger lines for this target

$ledger_block

## Frames for this turn

$frames_block

## Outcome classes

Report exactly one:
- negative — ruled something out with a stated range
- structure — a transferable insight, written under STRUCTURE in the notebook
- correction — overturned a prior recorded claim, with the reason, without deleting it
- verified — (adversarial turns only) re-derived a prior claim independently, with stated range
- counterexample — re-verified by a second, independent code path before recording
- frames — (forage turns only) filed at least one new frame with a source URL
- nothing — ran, found nothing, and wrote what was tried under SEARCHED

Set refinement to true when your ledger line only sharpens a fact an earlier
ledger line already states, such as a larger range for the same negative.

## Rules of the room

$honesty_rules

Novelty check is mandatory before recording anything as new: look it up
(OEIS, arXiv, web) and record the result in the NOVELTY field.

## Writing rules

- Allowed writes: $allowed_writes
- A productive outcome requires appending one line to .timeloop/ledger.md that
  must begin with `$turn_id | ` and follow the ledger's format.
- Update .timeloop/notebook/$notebook_slug.md using the schema in the README
  (STATUS, SEARCHED, RULED OUT, STRUCTURE, TECHNIQUE, NOVELTY, NEXT, COST).
  Open it if the index line above is not enough.
- Reusable code goes in .timeloop/lib/ with a test in .timeloop/tests/;
  throwaway probes go in .timeloop/runs/ as ${turn_id_lower}_*.py.
- Budget: 30 minutes. Prefer a smaller verified range over a larger unverified one.

## Result

Finish by replying with JSON matching this schema and nothing else:

```json
$result_schema
```

files_changed must list every path that exists at the end of your turn and
that you created or modified, relative to the repository root. frames_filed
entries need slug, title, statement, shape tags, and source with kind and
url; a source needs a url unless its kind is `own`.
