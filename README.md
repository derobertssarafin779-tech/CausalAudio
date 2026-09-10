# CausalAudio
# CausalAudio

Reproducibility materials for:

**CausalAudio: Counterfactual and Evidence-Aware Probing for Audio Question Answering**

## Overview

CausalAudio is an evaluation protocol for probing whether Audio Question Answering
(AudioQA) models respond consistently to controlled changes in acoustic evidence.

For each item, four response constraints are evaluated:

- **O**: original correctness
- **C**: correct adaptation to an answer-changing edit
- **P**: preservation under an answer-preserving edit
- **T**: text-only failure

Strict causal grounding (**SCG**) requires all four constraints to hold.

## Dataset

The evaluation uses **48 source items (Final-48)** derived from the MMAR benchmark.

Each source item has three audio conditions:

- original audio
- answer-changing edit
- answer-preserving edit

This gives **144 audio conditions** in total.

This repository does **not** redistribute MMAR audio files.
Source audio should be obtained from the official MMAR release.

The Final-48 manifest records source identifiers, questions, choices,
reference labels, intervention types, and edit parameters.

## Experiments

The repository contains archived outputs and evaluation artifacts for four settings:

1. **Primary experiment**
2. **Matched-wording sensitivity**
3. **Neutral-control Run 1**
4. **Neutral-control Run 2**

The primary experiment evaluates:

- Qwen3-Omni-Flash without thinking
- Qwen3-Omni-Flash with thinking
- Gemini-2.5-Flash
- Gemini-2.5-Pro

The two neutral-control runs include Qwen3-Omni-Flash without/with thinking
and Gemini-2.5-Flash.

## Repository contents

```text
data/
    Final-48 manifest and edit parameters

scripts/
    frozen parser
    scoring code
    metric computation
    intervention replay
    unknown-output bound computation

outputs/
    primary/
    matched_wording/
    neutral_run1/
    neutral_run2/

results/
    main metrics
    constraint-omission results
    audit-sensitivity results
    repeatability results

audit/
    human-audit records

supplementary/
    additional reproducibility documentation
