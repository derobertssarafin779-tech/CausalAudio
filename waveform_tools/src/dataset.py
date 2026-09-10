from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REQUIRED_CONDITIONS = {"original", "change", "preserve"}


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def project_root_from(start: str | Path) -> Path:
    path = Path(start).resolve()
    if path.is_file():
        path = path.parent
    for candidate in [path, *path.parents]:
        if (candidate / "configs" / "experiment.yaml").exists() and (candidate / "src").exists():
            return candidate
    return Path.cwd().resolve()


def resolve_project_path(path: str | Path, root: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else Path(root) / p


def validate_rows(
    rows: list[dict[str, Any]],
    root: str | Path,
    expected_samples: int = 48,
    expected_cases: int = 144,
) -> dict[str, Any]:
    root = Path(root)
    conditions = Counter(row.get("condition") for row in rows)
    key_counts = Counter((row.get("id"), row.get("condition")) for row in rows)
    duplicates = [key for key, count in key_counts.items() if count > 1]

    by_id: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    missing_audio: list[str] = []
    bad_expected: list[str] = []
    bad_preserve: list[str] = []

    for row in rows:
        row_id = row.get("id")
        condition = row.get("condition")
        if row_id is not None and condition is not None:
            by_id[str(row_id)][str(condition)] = row

        audio_path = row.get("audio_path")
        if not audio_path or not resolve_project_path(audio_path, root).exists():
            missing_audio.append(f"{row_id}:{condition}:{audio_path}")

        choices = row.get("choices") or []
        expected = row.get("expected_answer")
        if condition in {"original", "change", "preserve"} and expected not in choices:
            bad_expected.append(f"{row_id}:{condition}:{expected}")

    bad_condition_sets = {
        row_id: sorted(sample_rows)
        for row_id, sample_rows in by_id.items()
        if set(sample_rows) != REQUIRED_CONDITIONS
    }

    for row_id, sample_rows in by_id.items():
        if set(sample_rows) == REQUIRED_CONDITIONS:
            original_expected = sample_rows["original"].get("expected_answer")
            preserve_expected = sample_rows["preserve"].get("expected_answer")
            if preserve_expected != original_expected:
                bad_preserve.append(f"{row_id}: preserve={preserve_expected!r}, original={original_expected!r}")

    valid = (
        len(rows) == expected_cases
        and len(by_id) == expected_samples
        and conditions == Counter({"original": 48, "change": 48, "preserve": 48})
        and not duplicates
        and not missing_audio
        and not bad_condition_sets
        and not bad_expected
        and not bad_preserve
    )

    return {
        "valid": valid,
        "total_rows": len(rows),
        "unique_samples": len(by_id),
        "conditions": dict(conditions),
        "duplicates": duplicates,
        "missing_audio": missing_audio,
        "bad_condition_sets": bad_condition_sets,
        "bad_expected": bad_expected,
        "bad_preserve": bad_preserve,
    }

