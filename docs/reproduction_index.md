# Reproduction index

This file maps the main paper-facing evidence to the public archive.

## Core dataset and edit records

- `data/final48_manifest.jsonl`: 144 rows = 48 source items × 3 audio conditions.
- `data/final48_index.csv`: one row per source item with original/change/preserve references.
- `data/edit_parameters.csv`: answer-changing and answer-preserving operations and parameters.

## Archived response sets

- Protocol A / Primary: `outputs/primary/`
- Protocol B / Matched wording: `outputs/matched_wording/`
- Protocol C / Neutral Run 1: `outputs/neutral_run1/`
- Protocol D / Neutral Run 2: `outputs/neutral_run2/`

The public files retain raw response text plus the fields required for parsing/scoring. Provider-side response IDs, timing records, usage/billing fields, and other non-scoring metadata were removed from this public release.

## Frozen parsing rules

- A: `parsers/primary_prompt.py`
- B: `parsers/matched_wording_parser.py`
- C/D: `parsers/neutral_repeat_scoring.py`

Unknown responses remain unknown. No post-hoc parser rule is added by the public reproduction script.

## Main numerical reproduction

Run:

```bash
python scripts/reproduce_all.py
```

The script regenerates:

- Acc0, CAA@OC, IPS@OC, text accuracy, AN, CAA@AN, IPS@AN, SCG;
- constraint-omission counts;
- exhaustive unknown-output bounds;
- C/D constraint agreement and passing-set overlap;
- audit-subset omission sensitivity;
- Figure-2 diagnostic counts;
- the independently audited illustrative case.

Regenerated files are written to `results/recomputed/` and are programmatically checked against `results/reference/`.

## Table 1 / primary metrics

Reference: `results/reference/metrics.json` and `metrics.csv`.

Primary SCG counts:

- Qwen NT: 2/48
- Qwen T: 2/48
- Gemini Flash: 2/48
- Gemini Pro: 5/48

## Table 2 / omission analysis

Primary and audit-subset omission results:

- `results/reference/omission_sensitivity.json`
- `results/reference/omission_sensitivity.csv`

After excluding the 7 historically disputed items (`N=41`), adaptation-omission increments are `6, 4, 6, 5`.

## Unknown bounds

Gemini Flash Neutral Run 2 contains 12 unresolved constraint outcomes. `scripts/reproduce_all.py` enumerates all 4,096 assignments and reproduces:

- AN: 6–8/48
- CAA@AN: 14.29–28.57%
- IPS@AN: 33.33–50.00%
- SCG: 0–1/48

## Repeatability

Reference: `results/reference/overlap.json`.

- Qwen NT: identical O/C/P/T outcomes and the same 3 SCG passes.
- Qwen T: 6 → 5 SCG passes, 4 shared; Jaccard 4/7.
- Gemini Flash: 1 → 0–1 SCG passes; no possible shared SCG pass.

## Human-audit subset records

- `data/audit_subsets/row_comparison.json`: independently confirmed 12-item audit rows, with pseudonymous reviewer IDs.
- `data/audit_subsets/second_reviewer_triplet_triage.json`: fixed membership for the historical disputed/unresolved subsets.

These records support the reported sensitivity analyses but do not imply full 48-item human validation.

## Illustrative real item

`results/reference/illustrative_case.json` records the selected independently audited example, the post-hoc selection rule, all eligible IDs, references, interventions, predictions, and raw response text.
