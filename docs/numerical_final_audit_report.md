# CausalAudio numerical final-audit summary

**Release date:** 2026-09-10

## Result

The public-release reproduction script was executed from the cleaned archive and matched the frozen reference summaries for all four protocols. No paper-facing numerical correction was required.

## Main SCG counts

| Configuration | A: Primary | B: Matched wording | C: Neutral Run 1 | D: Neutral Run 2 |
| --- | ---: | ---: | ---: | ---: |
| Qwen NT | 2/48 | 3/48 | 3/48 | 3/48 |
| Qwen T | 2/48 | 3/48 | 6/48 | 5/48 |
| Gemini Flash | 2/48 | 0/48 | 1/48 | 0–1/48 |
| Gemini Pro | 5/48 | 4/48 | — | — |

## Unknown-output bounds

For Gemini Flash Neutral Run 2, 12 unresolved constraint outcomes are exhaustively enumerated (`2^12 = 4,096` assignments). The reproduced bounds are:

- AN: 6–8/48
- CAA@AN: 14.29–28.57%
- IPS@AN: 33.33–50.00%
- SCG: 0–1/48

These are feasible identification bounds over unresolved outputs, not confidence intervals.

## Audit-sensitive omission analysis

The primary SCG counts remain 2, 2, 2, 5 after excluding either the 4 intermediate-stage unresolved items (`N=44`) or the 7 historically disputed items (`N=41`). After excluding the 7 disputed items, adaptation-omission increments are 6, 4, 6, 5. In the independently confirmed 12-item subset, SCG counts are 0, 2, 1, 2 and adaptation increments are 3, 0, 4, 0.

These checks are sensitivity analyses. They do not relabel items or prove semantic validity of every reference label.

## Repeatability

Across the two neutral runs:

- Qwen NT reproduces all four constraint outcomes for all 48 items and the same 3 SCG passes.
- Qwen T changes from 6 to 5 SCG passes, sharing 4 passes (Jaccard 4/7).
- Gemini Flash changes from 1 to 0–1 SCG passes under unknown-output bounds, with no possible shared pass.

## Public-release sanitation

The reviewer-facing archive removes machine-specific absolute paths, internal historical replay adapters, duplicate manuscript snapshots, nested previous archives, provider response IDs, request timing logs, and usage/billing metadata. Raw model response text and all fields needed for parsing and scoring are retained.

The cleaned archive was then re-run with `python scripts/reproduce_all.py`; all public reference comparisons passed.
