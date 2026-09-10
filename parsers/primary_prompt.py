from __future__ import annotations

import re


def make_prompt(question: str, choices: list[str]) -> str:
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    option_text = "\n".join(
        f"{letters[i]}. {choice}" for i, choice in enumerate(choices)
    )
    return (
        "Listen carefully to the audio and answer the multiple-choice question.\n"
        "Base your answer only on the current audio.\n\n"
        f"Question: {question}\n"
        f"Options:\n{option_text}\n\n"
        "Return exactly one line in this format:\n"
        "FINAL: <OPTION LETTER>"
    )


def parse_prediction(text: str, choices: list[str]) -> tuple[str | None, str | None]:
    up = text.upper()
    m = re.search(r"FINAL\s*:\s*([A-Z])", up)
    if not m:
        m = re.search(r"(?:ANSWER|OPTION)\s*(?:IS|:)?\s*([A-Z])\b", up)
    if not m:
        letters = "".join(chr(ord("A") + i) for i in range(len(choices)))
        hits = re.findall(rf"\b([{letters}])\b", up)
        if hits:
            letter = hits[-1]
        else:
            return None, None
    else:
        letter = m.group(1)

    idx = ord(letter) - ord("A")
    if idx < 0 or idx >= len(choices):
        return letter, None
    return letter, choices[idx]



def make_text_only_prompt(question: str, choices: list[str]) -> str:
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    option_text = "\n".join(
        f"{letters[i]}. {choice}" for i, choice in enumerate(choices)
    )
    return (
        "Answer the multiple-choice question without access to the audio.\n"
        "Use only the question and answer options. If the audio is necessary, make your best guess.\n\n"
        f"Question: {question}\n"
        f"Options:\n{option_text}\n\n"
        "Return exactly one line in this format:\n"
        "FINAL: <OPTION LETTER>"
    )
