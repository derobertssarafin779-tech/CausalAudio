#!/usr/bin/env python3
"""Verify SHA-256 hashes listed in SHA256SUMS_RELEASE.txt."""
from pathlib import Path
import hashlib
import sys

ROOT = Path(__file__).resolve().parents[1]
manifest = ROOT / "SHA256SUMS_RELEASE.txt"
if not manifest.exists():
    raise SystemExit("Missing SHA256SUMS_RELEASE.txt")

failures = []
checked = 0
for line in manifest.read_text(encoding="utf-8").splitlines():
    if not line.strip() or line.startswith("#"):
        continue
    digest, rel = line.split("  ", 1)
    path = ROOT / rel
    if not path.is_file():
        failures.append((rel, "missing"))
        continue
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    checked += 1
    if actual != digest:
        failures.append((rel, actual))

if failures:
    print(f"SHA-256 verification FAILED: {len(failures)} problem(s)")
    for rel, status in failures[:20]:
        print(" -", rel, status)
    sys.exit(1)
print(f"SHA-256 verification PASS: {checked} files")
