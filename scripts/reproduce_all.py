#!/usr/bin/env python3
"""Recompute the numerical analyses reported for CausalAudio.

This public-release script uses only archived model responses, the Final-48
manifest, and the frozen response parsers. It never calls a model API and
requires only the Python standard library.

Outputs are written under results/recomputed/. Unknown responses remain
unknown; affected metrics are bounded by exhaustive enumeration of every
feasible assignment (up to 2^12 = 4096 assignments in the released runs).
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import csv
import hashlib
import importlib.util
import itertools
import json
import math

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "recomputed"
OUT.mkdir(parents=True, exist_ok=True)

CONFIGS = {
    "qwen_omni_nonthinking": "qwen3_omni_flash_nonthinking",
    "qwen_omni_thinking": "qwen3_omni_flash_thinking",
    "gemini_302_flash": "gemini_2_5_flash_302",
    "gemini_302_pro": "gemini_2_5_pro_302",
}
CONDS = ["original", "change", "preserve", "text_only"]
METRICS = ["Acc0", "CAA_OC", "IPS_OC", "TextAcc", "AN", "CAA_AN", "IPS_AN", "SCG"]


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def evaluate(complete_flags):
    """Return metric (numerator, denominator) pairs and omission increments."""
    o = sum(f[0] for f in complete_flags)
    an = sum(f[0] and f[3] for f in complete_flags)
    full = sum(all(f) for f in complete_flags)
    numerators = [
        o,
        sum(f[0] and f[1] for f in complete_flags),
        sum(f[0] and f[2] for f in complete_flags),
        sum(not f[3] for f in complete_flags),
        an,
        sum(f[0] and f[1] and f[3] for f in complete_flags),
        sum(f[0] and f[2] and f[3] for f in complete_flags),
        full,
    ]
    denominators = [48, o, o, 48, 48, an, an, 48]
    omission = [
        sum(all(f[k] for k in range(4) if k != j) for f in complete_flags) - full
        for j in range(4)
    ]
    return list(zip(numerators, denominators)), omission


def exhaustive(flags_by_id, ids):
    """Enumerate all assignments to unknown constraint values."""
    work = [list(flags_by_id[i]) for i in ids]
    unknown = [(row_i, k) for row_i, f in enumerate(work) for k, v in enumerate(f) if v is None]
    metric_states = [set() for _ in METRICS]
    omission_states = [set() for _ in range(4)]

    for bits in itertools.product([False, True], repeat=len(unknown)):
        for (row_i, k), value in zip(unknown, bits):
            work[row_i][k] = value
        pairs, omissions = evaluate(work)
        for state, pair in zip(metric_states, pairs):
            state.add(tuple(map(int, pair)))
        for state, value in zip(omission_states, omissions):
            state.add(int(value))

    result = {}
    for label, state in zip(METRICS, metric_states):
        valid_percent = [100 * k / n for k, n in state if n]
        result[label] = {
            "numerator": [min(k for k, _ in state), max(k for k, _ in state)],
            "denominator": [min(n for _, n in state), max(n for _, n in state)],
            "percent": [min(valid_percent), max(valid_percent)] if valid_percent else [None, None],
            "feasible_count_pairs": [list(x) for x in sorted(state)],
            "undefined_possible": any(n == 0 for _, n in state),
        }
    omission = {
        key: [min(state), max(state)]
        for key, state in zip("OCPT", omission_states)
    }
    return result, omission, len(unknown)


def wilson(k: int, n: int):
    z = 1.959963984540054
    p = k / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [100 * (center - half), 100 * (center + half)]


primary_parser = load_module(ROOT / "parsers" / "primary_prompt.py", "primary_parser")
matched_parser = load_module(ROOT / "parsers" / "matched_wording_parser.py", "matched_parser")
neutral_parser = load_module(ROOT / "parsers" / "neutral_repeat_scoring.py", "neutral_parser")

manifest = read_jsonl(ROOT / "data" / "final48_manifest.jsonl")
M = {(r["id"], r["condition"]): r for r in manifest}
IDS = sorted({r["id"] for r in manifest})
assert len(IDS) == 48 and len(manifest) == 144
assert all(
    M[i, "preserve"]["expected_answer"] == M[i, "original"]["expected_answer"]
    and M[i, "change"]["expected_answer"] != M[i, "original"]["expected_answer"]
    for i in IDS
)

flags = {}
records = {}
parse_rows = []

# A: primary experiment.
for cfg, primary_name in CONFIGS.items():
    audio_rows = read_jsonl(ROOT / "outputs" / "primary" / primary_name / "seed_42" / "predictions.jsonl")
    text_rows = read_jsonl(ROOT / "outputs" / "primary" / f"{primary_name}_text_only" / "seed_42" / "text_only_predictions.jsonl")
    for row in text_rows:
        row = row  # explicit: no mutation is needed beyond local condition/reference handling
    rr = audio_rows + text_rows
    assert len(rr) == 192
    f = {i: {} for i in IDS}
    normalized = []
    for row in rr:
        condition = row.get("condition", "text_only")
        ref = M[row["id"], condition if condition != "text_only" else "original"]
        choices = row["choices"]
        letter, prediction = primary_parser.parse_prediction(row["raw_response"], choices)
        stored_prediction = row.get("answer_prediction")
        assert prediction == stored_prediction
        assert row["question"] == ref["question"] and choices == ref["choices"]
        expected = row.get("expected_answer", row.get("original_answer"))
        assert expected == ref["expected_answer"]
        correct = prediction == expected
        f[row["id"]][condition] = correct
        normalized.append({**row, "condition": condition, "expected_answer": expected})
        parse_rows.append({
            "run": "A", "config": cfg, "id": row["id"], "condition": condition,
            "prediction": prediction, "correct": correct, "rule": "primary_parser",
        })
    records["A", cfg] = normalized
    flags["A", cfg] = {
        i: [f[i]["original"], f[i]["change"], f[i]["preserve"], not f[i]["text_only"]]
        for i in IDS
    }

# B: matched-wording text-only sensitivity; reuse A audio flags.
for cfg in CONFIGS:
    rows = read_jsonl(ROOT / "outputs" / "matched_wording" / cfg / "text_only_predictions.jsonl")
    assert len(rows) == 48 and {r["id"] for r in rows} == set(IDS)
    f = {i: list(flags["A", cfg][i]) for i in IDS}
    for row in rows:
        ref = M[row["id"], "original"]
        assert row["question"] == ref["question"] and row["choices"] == ref["choices"]
        assert row["original_answer"] == ref["expected_answer"]
        prediction, rule = matched_parser.extract(row["raw_response"], row["choices"])
        correct = prediction == ref["expected_answer"] if prediction is not None else None
        f[row["id"]][3] = (not correct) if correct is not None else None
        parse_rows.append({
            "run": "B", "config": cfg, "id": row["id"], "condition": "text_only",
            "prediction": prediction, "correct": correct, "rule": rule,
        })
    records["B", cfg] = rows
    flags["B", cfg] = f

# C/D: two neutral-prompt runs, using the frozen neutral parser.
for run, folder in [("C", "neutral_run1"), ("D", "neutral_run2")]:
    for cfg in list(CONFIGS)[:3]:
        rows = read_jsonl(ROOT / "outputs" / folder / cfg / "predictions.jsonl")
        ok = [r for r in rows if r["status"] == "ok"]
        assert len(ok) == 192
        assert {(r["id"], r["condition"]) for r in ok} == {(i, c) for i in IDS for c in CONDS}
        for row in ok:
            ref = M[row["id"], row["condition"] if row["condition"] != "text_only" else "original"]
            assert row["question"] == ref["question"] and row["choices"] == ref["choices"]
            assert row["expected_answer"] == ref["expected_answer"]
            prediction, rule = neutral_parser.extract(row)
            correct = prediction == row["expected_answer"] if prediction is not None else None
            parse_rows.append({
                "run": run, "config": cfg, "id": row["id"], "condition": row["condition"],
                "prediction": prediction, "correct": correct, "rule": rule,
            })
        records[run, cfg] = ok
        flags[run, cfg] = neutral_parser.flags(ok)
        assert len(flags[run, cfg]) == 48

# Aggregate metrics and exhaustive unknown bounds.
reports = {}
for (run, cfg), fs in flags.items():
    metrics, omission, n_unknown = exhaustive(fs, IDS)
    prs = [r for r in parse_rows if r["run"] == run and r["config"] == cfg]
    text = [r for r in prs if r["condition"] == "text_only"]
    definite = sorted(i for i, f in fs.items() if all(v is True for v in f))
    possible = sorted(i for i, f in fs.items() if not any(v is False for v in f))
    reports.setdefault(run, {})[cfg] = {
        "metrics": metrics,
        "omission_extra": omission,
        "unknown_constraints": n_unknown,
        "unknown_records": dict(Counter(r["condition"] for r in prs if r["correct"] is None)),
        "parse_counts": dict(Counter(r["rule"] for r in prs)),
        "text_correct": sum(r["correct"] is True for r in text),
        "text_answered": sum(r["correct"] is not None for r in text),
        "definite_passes": definite,
        "possible_passes": possible,
    }

# Cross-run repeatability for C/D.
overlap = {}
for cfg in list(CONFIGS)[:3]:
    agree = {}
    for k, label in enumerate("OCPT"):
        pairs = [(flags["C", cfg][i][k], flags["D", cfg][i][k]) for i in IDS]
        known = [(a, b) for a, b in pairs if a is not None and b is not None]
        agree[label] = {
            "agree": sum(a == b for a, b in known),
            "known_pairs": len(known),
            "unknown_pairs": 48 - len(known),
            "true_to_false": sum(a and not b for a, b in known),
            "false_to_true": sum((not a) and b for a, b in known),
        }
    definite = [set(reports[run][cfg]["definite_passes"]) for run in ["C", "D"]]
    possible = [set(reports[run][cfg]["possible_passes"]) for run in ["C", "D"]]
    vals = []
    undecided = [sorted(p - d) for d, p in zip(definite, possible)]
    for b1 in itertools.product([False, True], repeat=len(undecided[0])):
        for b2 in itertools.product([False, True], repeat=len(undecided[1])):
            sets = [
                definite[0] | {i for i, b in zip(undecided[0], b1) if b},
                definite[1] | {i for i, b in zip(undecided[1], b2) if b},
            ]
            den = len(sets[0] | sets[1])
            vals.append(len(sets[0] & sets[1]) / den if den else None)
    overlap[cfg] = {
        "agreement": agree,
        "intersection": len(definite[0] & definite[1]),
        "union_definite": len(definite[0] | definite[1]),
        "definite_sets": [sorted(x) for x in definite],
        "possible_sets": [sorted(x) for x in possible],
        "jaccard_bounds": [min(v for v in vals if v is not None), max(v for v in vals if v is not None)],
    }

# Audit-subset sensitivity and Table 2 omission sensitivity.
triage = json.loads((ROOT / "data" / "audit_subsets" / "second_reviewer_triplet_triage.json").read_text(encoding="utf-8"))
confirmed_rows = json.loads((ROOT / "data" / "audit_subsets" / "row_comparison.json").read_text(encoding="utf-8"))
confirmed = {r["id"] for r in confirmed_rows}
disputed = {r["rawId"] for r in triage}
unresolved = {r["rawId"] for r in triage if not r["second_supports_all_three_gold_labels"]}
assert (len(confirmed), len(disputed), len(unresolved)) == (12, 7, 4)
subsets = {
    "all48": set(IDS),
    "exclude_unresolved4": set(IDS) - unresolved,
    "exclude_disputed7": set(IDS) - disputed,
    "confirmed12": confirmed,
}
omission_sensitivity = {}
omission_rows = []
for subset_name, keep in subsets.items():
    omission_sensitivity[subset_name] = {}
    for cfg in CONFIGS:
        subset_flags = [flags["A", cfg][i] for i in sorted(keep)]
        full = sum(all(f) for f in subset_flags)
        extra = {
            key: sum(all(f[q] for q in range(4) if q != n) for f in subset_flags) - full
            for n, key in enumerate("OCPT")
        }
        extra_ids = {
            key: sorted(
                i for i in keep
                if flags["A", cfg][i][n] is False
                and all(flags["A", cfg][i][q] for q in range(4) if q != n)
            )
            for n, key in enumerate("OCPT")
        }
        omission_sensitivity[subset_name][cfg] = {
            "N": len(keep), "SCG": full, "omission_extra": extra, "extra_item_ids": extra_ids,
        }
        omission_rows.append({"subset": subset_name, "config": cfg, "N": len(keep), "SCG": full, **extra})

# Figure 2 counts (primary Qwen original-correct subsets).
figure2 = {}
for cfg in list(CONFIGS)[:2]:
    lookup = {(r["id"], r["condition"]): r for r in records["A", cfg]}
    oc = [i for i in IDS if flags["A", cfg][i][0]]
    inertia = sum(lookup[i, "change"]["answer_prediction"] == lookup[i, "original"]["answer_prediction"] for i in oc)
    adaptation = sum(flags["A", cfg][i][1] for i in oc)
    misdirected = len(oc) - adaptation - inertia
    spurious = sum(not flags["A", cfg][i][2] for i in oc)
    figure2[cfg] = {
        "N_OC": len(oc), "adaptation": adaptation, "inertia": inertia,
        "misdirected": misdirected, "spurious": spurious,
    }

# Independently audited illustrative failure case, using the documented post-hoc rule.
eligible = []
for i in sorted(confirmed):
    if flags["A", "qwen_omni_nonthinking"][i] == [True, False, True, True]:
        eligible.append(i)
chosen = eligible[0]
lookup = {(r["id"], r["condition"]): r for r in records["A", "qwen_omni_nonthinking"]}
case = {
    "selection": "Post-hoc illustration: lexicographically first independently confirmed primary Qwen NT item with O,C,P,T = 1,0,1,1. Not a prevalence estimate.",
    "eligible_item_ids": eligible,
    "id": chosen,
    "configuration": "qwen_omni_nonthinking",
    "question": M[chosen, "original"]["question"],
    "choices": M[chosen, "original"]["choices"],
    "flags": flags["A", "qwen_omni_nonthinking"][chosen],
    "records": [],
}
for condition in CONDS:
    row = lookup[chosen, condition]
    ref = M[chosen, condition if condition != "text_only" else "original"]
    case["records"].append({
        "condition": condition,
        "reference": ref["expected_answer"],
        "intervention": ref.get("intervention"),
        "prediction": row["answer_prediction"],
        "raw_response": row["raw_response"],
    })

# Write results.
write_json(OUT / "metrics.json", reports)
write_json(OUT / "item_flags.json", {run: {cfg: flags[run, cfg] for cfg in reports[run]} for run in reports})
write_json(OUT / "overlap.json", overlap)
write_json(OUT / "omission_sensitivity.json", omission_sensitivity)
write_json(OUT / "figure2_counts.json", figure2)
write_json(OUT / "illustrative_case.json", case)
with (OUT / "metrics.csv").open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["run", "configuration", "metric", "numerator_min", "numerator_max", "denominator_min", "denominator_max", "percent_min", "percent_max"])
    for run, configs in reports.items():
        for cfg, report in configs.items():
            for metric, m in report["metrics"].items():
                writer.writerow([run, cfg, metric, *m["numerator"], *m["denominator"], *m["percent"]])
with (OUT / "omission_sensitivity.csv").open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["subset", "config", "N", "SCG", "O", "C", "P", "T"])
    writer.writeheader()
    writer.writerows(omission_rows)

# Validate the public recomputation against the frozen reference summaries.
reference = json.loads((ROOT / "results" / "reference" / "metrics.json").read_text(encoding="utf-8"))
for run, configs in reports.items():
    for cfg, report in configs.items():
        ref = reference[run][cfg]
        assert report["metrics"] == ref["metrics"], (run, cfg, "metrics")
        assert report["omission_extra"] == ref["omission_extra"], (run, cfg, "omission")
        assert report["unknown_constraints"] == ref["unknown_constraints"], (run, cfg, "unknown")

ref_omission = json.loads((ROOT / "results" / "reference" / "omission_sensitivity.json").read_text(encoding="utf-8"))
assert omission_sensitivity == ref_omission
assert figure2 == json.loads((ROOT / "results" / "reference" / "figure2_counts.json").read_text(encoding="utf-8"))
assert case == json.loads((ROOT / "results" / "reference" / "illustrative_case.json").read_text(encoding="utf-8"))

# Key paper-facing checks, printed for quick inspection.
print("CausalAudio public reproduction: PASS")
print("Source items:", len(IDS), "| audio conditions:", len(manifest))
for run in ["A", "B", "C", "D"]:
    values = []
    for cfg in reports[run]:
        n = reports[run][cfg]["metrics"]["SCG"]["numerator"]
        values.append(f"{cfg}={n[0]}" if n[0] == n[1] else f"{cfg}={n[0]}-{n[1]}")
    print(f"SCG {run}:", ", ".join(values))
flash_d = reports["D"]["gemini_302_flash"]
print("Flash D unknown constraints:", flash_d["unknown_constraints"], "(4096 assignments)")
print("Flash D AN:", flash_d["metrics"]["AN"]["numerator"], "/48")
print("Flash D CAA@AN %:", [round(x, 2) for x in flash_d["metrics"]["CAA_AN"]["percent"]])
print("Flash D IPS@AN %:", [round(x, 2) for x in flash_d["metrics"]["IPS_AN"]["percent"]])
print("Exclude disputed-7 adaptation increments:", [omission_sensitivity["exclude_disputed7"][cfg]["omission_extra"]["C"] for cfg in CONFIGS])
print("Primary SCG Wilson 95%% intervals: 2/48 = %.2f-%.2f%%; 5/48 = %.2f-%.2f%%" % (*wilson(2,48), *wilson(5,48)))
print("Outputs written to:", OUT.relative_to(ROOT))
