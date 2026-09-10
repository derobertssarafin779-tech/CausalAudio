# Prompt and parsing summary

This document records the prompt families relevant to the released numerical analyses.

## A — Primary audio

```text
Listen carefully to the audio and answer the multiple-choice question.
Base your answer only on the current audio.

Question: <QUESTION>
Options:
A. <CHOICE A>
B. <CHOICE B>
...

Return exactly one line in this format:
FINAL: <OPTION LETTER>
```

## A — Primary text-only

```text
Answer the multiple-choice question without access to the audio.
Use only the question and answer options. If the audio is necessary, make your best guess.

Question: <QUESTION>
Options:
A. <CHOICE A>
B. <CHOICE B>
...

Return exactly one line in this format:
FINAL: <OPTION LETTER>
```

The exact construction functions and primary parser are in `parsers/primary_prompt.py`.

## B — Matched-wording text-only sensitivity

Protocol B supplies the primary audio-request wording without audio. The historical extraction rule accepts either an exact `FINAL: <OPTION LETTER>` line or the documented terminal boxed form; unresolved outputs remain unknown. See `parsers/matched_wording_parser.py`.

## C/D — Neutral prompt

All four conditions use the same request wording:

```text
Answer the multiple-choice question using the available input.

Question: <QUESTION>
Options:
A. <CHOICE A>
B. <CHOICE B>
...

Return exactly one line in this format:
FINAL: <OPTION LETTER>
```

C and D use the same frozen extraction module in `parsers/neutral_repeat_scoring.py`.

## Request settings relevant to interpretation

- seed: 42
- Qwen thinking mode: toggled by configuration
- temperature: not explicitly set
- token limit: not explicitly set
- backend version snapshots: not recorded

The public archive reproduces scoring from archived responses; it does not guarantee byte-identical regeneration of new API responses.
