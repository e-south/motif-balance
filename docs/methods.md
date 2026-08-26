---
doc_id: motif-balance-methods
title: Motif Balance methods
intent: State the software method precisely enough for replay and review.
audience:
  - users
  - integrators
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-26
doc_type: reference
---

# Motif Balance methods

For each candidate sequence, Motif Balance enumerates valid placements for each
declared motif and strand. It scores each placement through the versioned
scoring authority, selects one best match with a deterministic total-order tie
break, and normalizes the selected score using the model's declared reference
domain. The reported candidate score is the hard minimum across motifs.

For a tractable sequence space, search evaluates every sequence. Larger spaces
use a versioned multi-start annealed engine. Starts share one seeded origin and
receive deterministic perturbations. The engine mixes single-base Gibbs-style
updates, contiguous-block replacements, multi-position replacements, and motif
insertions. Proposals may target the current limiting motif. A smooth minimum
guides proposals and a separate inverse-temperature schedule controls
acceptance; neither value is a public score.

The budget counts calls to the authoritative evaluator, including the four
candidate evaluations used by a single-base update. Once evaluated, a sequence
and its matches are immutable. Search records bounded best-score checkpoints,
restart-final scores, and proposal counts. Selection applies deterministic
ordering and any declared distance rule to return exactly the requested
portfolio size without constraint relaxation.

The canonical bundle writes the normalized request, motif content, candidate
table, long-form match table, and complete manifest. Publication is atomic and
refuses an existing output path. Replay records package, schema, scoring,
search-engine, RNG, seed, budget, diagnostic, and artifact versions.

This document defines software behavior. A study must separately define its
task cohort, baselines, repetitions, statistical analysis, evidence acceptance,
and claim boundary.
