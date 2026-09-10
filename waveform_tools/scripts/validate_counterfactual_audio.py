#!/usr/bin/env python3
"""Replay and verify every deterministic audio intervention in Final-48.

This is an automatic construction check.  It verifies that each saved change
or preserve waveform can be recreated from its original waveform and the
operation parameters recorded in the manifest.  It does not make a human
semantic-auditing claim about the source AudioQA labels.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.dataset import load_jsonl, resolve_project_path

REQUIRED_CONDITIONS = {"original", "change", "preserve"}
DEFAULT_TOLERANCE = 4e-5  # PCM16 quantization is at most about 3.1e-5.


def sec_to_idx(seconds: float, sample_rate: int, length: int) -> int:
    return max(0, min(length, int(round(float(seconds) * sample_rate))))


def ensure_2d(audio: np.ndarray) -> tuple[np.ndarray, bool]:
    if audio.ndim == 1:
        return audio[:, None], True
    return audio, False


def restore_dim(audio: np.ndarray, was_mono: bool) -> np.ndarray:
    return audio[:, 0] if was_mono else audio


def resample_speed(audio: np.ndarray, factor: float) -> np.ndarray:
    if factor <= 0:
        raise ValueError("tempo factor must be positive")
    length = len(audio)
    output_length = max(1, int(round(length / factor)))
    old_x = np.arange(length, dtype=np.float64)
    new_x = np.linspace(0, length - 1, output_length, dtype=np.float64)
    output = np.empty((output_length, audio.shape[1]), dtype=np.float64)
    for channel in range(audio.shape[1]):
        output[:, channel] = np.interp(new_x, old_x, audio[:, channel])
    return output.astype(audio.dtype, copy=False)


def apply_operation(
    audio: np.ndarray, sample_rate: int, operation: str, params: dict[str, Any]
) -> np.ndarray:
    """Match the deterministic generator used for the released manifest."""
    result, was_mono = ensure_2d(audio.copy())
    length = len(result)

    if operation == "mute":
        start = sec_to_idx(params["start"], sample_rate, length)
        end = sec_to_idx(params["end"], sample_rate, length)
        result[start:end] = 0

    elif operation == "multi_mute":
        intervals = params.get("intervals", [])
        if not intervals:
            raise ValueError("multi_mute requires non-empty intervals")
        for start_seconds, end_seconds in intervals:
            start = sec_to_idx(start_seconds, sample_rate, length)
            end = sec_to_idx(end_seconds, sample_rate, length)
            if end <= start:
                raise ValueError(f"invalid multi_mute interval: {(start_seconds, end_seconds)}")
            result[start:end] = 0

    elif operation == "gain":
        start = sec_to_idx(params["start"], sample_rate, length)
        end = sec_to_idx(params["end"], sample_rate, length)
        amplitude = 10 ** (float(params["db"]) / 20.0)
        result[start:end] *= amplitude

    elif operation == "reverse":
        start = sec_to_idx(params["start"], sample_rate, length)
        end = sec_to_idx(params["end"], sample_rate, length)
        result[start:end] = result[start:end][::-1]

    elif operation == "swap":
        a_start = sec_to_idx(params["a_start"], sample_rate, length)
        a_end = sec_to_idx(params["a_end"], sample_rate, length)
        b_start = sec_to_idx(params["b_start"], sample_rate, length)
        b_end = sec_to_idx(params["b_end"], sample_rate, length)
        if not (a_end <= b_start or b_end <= a_start):
            raise ValueError("swap intervals overlap")
        if (a_end - a_start) != (b_end - b_start):
            raise ValueError("swap intervals have unequal lengths")
        held = result[a_start:a_end].copy()
        result[a_start:a_end] = result[b_start:b_end]
        result[b_start:b_end] = held

    elif operation == "pad_front":
        seconds = float(params["seconds"])
        if seconds < 0:
            raise ValueError("pad_front seconds must be non-negative")
        padding = np.zeros(
            (int(round(seconds * sample_rate)), result.shape[1]), dtype=result.dtype
        )
        result = np.concatenate([padding, result], axis=0)

    elif operation == "trim_front":
        start = sec_to_idx(params["seconds"], sample_rate, length)
        result = result[start:]
        if len(result) == 0:
            raise ValueError("trim_front removed the whole waveform")

    elif operation == "tempo":
        result = resample_speed(result, float(params["factor"]))

    elif operation == "rotate":
        split = sec_to_idx(params["split"], sample_rate, length)
        if split <= 0 or split >= length:
            raise ValueError("rotate split must be inside waveform")
        result = np.concatenate([result[split:], result[:split]], axis=0)

    elif operation == "repeat":
        times = int(params.get("times", 2))
        gap_seconds = float(params.get("gap_seconds", 0.0))
        if times < 2 or gap_seconds < 0:
            raise ValueError("invalid repeat parameters")
        gap = np.zeros(
            (int(round(gap_seconds * sample_rate)), result.shape[1]), dtype=result.dtype
        )
        pieces: list[np.ndarray] = []
        for index in range(times):
            if index and len(gap):
                pieces.append(gap.copy())
            pieces.append(result.copy())
        result = np.concatenate(pieces, axis=0)

    else:
        raise ValueError(f"unsupported operation: {operation}")

    return restore_dim(result, was_mono)


def read_audio(path: Path) -> tuple[np.ndarray, int]:
    audio, sample_rate = sf.read(path, dtype="float64", always_2d=False)
    if audio.size == 0:
        raise ValueError("empty waveform")
    if not np.isfinite(audio).all():
        raise ValueError("waveform contains non-finite values")
    return audio, sample_rate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="data/final_manifest.jsonl")
    parser.add_argument("--out", default="artifacts/counterfactual_audio_validation.json")
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
    args = parser.parse_args()

    manifest_path = ROOT / args.manifest
    out_path = ROOT / args.out
    rows = load_jsonl(manifest_path)
    by_id: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    errors: list[str] = []
    operation_counts: Counter[str] = Counter()
    replay_diagnostics: list[dict[str, Any]] = []

    for row in rows:
        sample_id = str(row.get("id", ""))
        condition = str(row.get("condition", ""))
        if condition not in REQUIRED_CONDITIONS:
            errors.append(f"{sample_id}: unsupported condition {condition!r}")
            continue
        if condition in by_id[sample_id]:
            errors.append(f"{sample_id}: duplicate {condition} row")
        by_id[sample_id][condition] = row

        choices = row.get("choices") or []
        if row.get("expected_answer") not in choices:
            errors.append(f"{sample_id}:{condition}: expected answer is not a choice")

    replay_verified = 0
    replay_failed = 0
    decoded_files = 0
    for sample_id, triplet in sorted(by_id.items()):
        if set(triplet) != REQUIRED_CONDITIONS:
            errors.append(f"{sample_id}: conditions={sorted(triplet)}")
            continue

        original = triplet["original"]
        preserve = triplet["preserve"]
        change = triplet["change"]
        if original.get("expected_answer") != original.get("original_answer"):
            errors.append(f"{sample_id}: original expected answer differs from original_answer")
        if preserve.get("expected_answer") != original.get("expected_answer"):
            errors.append(f"{sample_id}: preserve label differs from original label")
        if change.get("expected_answer") == original.get("expected_answer"):
            errors.append(f"{sample_id}: change label did not change")
        if original.get("intervention") is not None:
            errors.append(f"{sample_id}: original row must not have an intervention")

        try:
            original_audio, original_sr = read_audio(
                resolve_project_path(original["audio_path"], ROOT)
            )
            decoded_files += 1
        except Exception as exc:  # noqa: BLE001 - include path-level validation errors.
            errors.append(f"{sample_id}:original: cannot decode audio ({exc})")
            continue

        for condition in ("change", "preserve"):
            row = triplet[condition]
            intervention = row.get("intervention") or {}
            operation = intervention.get("op")
            params = intervention.get("params")
            if not isinstance(operation, str) or not isinstance(params, dict):
                errors.append(f"{sample_id}:{condition}: malformed intervention")
                replay_failed += 1
                continue
            operation_counts[operation] += 1
            try:
                expected_audio = apply_operation(original_audio, original_sr, operation, params)
                saved_audio, saved_sr = read_audio(resolve_project_path(row["audio_path"], ROOT))
                decoded_files += 1
                if saved_sr != original_sr:
                    raise ValueError(f"sample rate {saved_sr} != original {original_sr}")
                if saved_audio.shape != expected_audio.shape:
                    raise ValueError(
                        f"shape {saved_audio.shape} != reconstructed {expected_audio.shape}"
                    )
                max_abs_error = float(np.max(np.abs(saved_audio - expected_audio)))
                status = "pass" if max_abs_error <= args.tolerance else "fail"
                replay_diagnostics.append(
                    {
                        "id": sample_id,
                        "condition": condition,
                        "operation": operation,
                        "max_abs_error": max_abs_error,
                        "status": status,
                    }
                )
                if status == "pass":
                    replay_verified += 1
                else:
                    replay_failed += 1
                    errors.append(
                        f"{sample_id}:{condition}: max abs error {max_abs_error:.8f} "
                        f"exceeds tolerance {args.tolerance:.8f}"
                    )
            except Exception as exc:  # noqa: BLE001 - keep all sample-level errors in the report.
                replay_failed += 1
                errors.append(f"{sample_id}:{condition}: replay failed ({exc})")

    summary = {
        "scope": "automatic deterministic construction validation; not human semantic audit",
        "manifest": str(Path(args.manifest)),
        "manifest_rows": len(rows),
        "unique_samples": len(by_id),
        "decoded_files": decoded_files,
        "replay_verified_variants": replay_verified,
        "replay_failed_variants": replay_failed,
        "tolerance": args.tolerance,
        "operation_counts": dict(sorted(operation_counts.items())),
        "errors": errors,
        "diagnostics": replay_diagnostics,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if errors:
        print("COUNTERFACTUAL AUDIO VALIDATION FAILED")
        print(f"errors = {len(errors)}")
        print(f"report = {out_path}")
        raise SystemExit(1)

    print("COUNTERFACTUAL AUDIO VALIDATION PASSED")
    print(f"{len(by_id)} complete triplets / {replay_verified} replay-verified variants")
    print(f"decoded files = {decoded_files}")
    print(f"report = {out_path}")


if __name__ == "__main__":
    main()
