"""Historical parser used for the matched-wording text-only sensitivity run.

The extraction policy is intentionally narrow and mirrors the rule used in the
reported analysis: accept either an exact `FINAL: <LETTER>` line or a terminal
`The final answer is $\\boxed{<LETTER>}$` statement. Anything else remains
unknown. No heuristic recovery is added here.
"""
from __future__ import annotations
import re


def extract(raw_response: str, choices: list[str]):
    match = re.fullmatch(r"\s*FINAL\s*:\s*([A-Z])\s*", raw_response, re.I)
    rule = "strict_final"
    if not match:
        match = re.search(
            r"The final answer is \$\\boxed\{([A-Z])\}\$\s*$",
            raw_response,
        )
        rule = "explicit_terminal_boxed"
    if not match:
        return None, "undetermined"
    index = ord(match.group(1).upper()) - 65
    if index < 0 or index >= len(choices):
        return None, "invalid_option"
    return choices[index], rule
