---
doc_id: motif-balance-methods
title: Motif Balance methods
intent: State the software method precisely enough for replay and review.
audience:
  - users
  - integrators
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-30
doc_type: reference
---

# Motif Balance methods

For each candidate sequence, Motif Balance enumerates valid placements for each
declared motif and strand. It scores each placement through the versioned
scoring authority, selects one best match with a deterministic total-order tie
break, and normalizes the selected score using the model's declared reference
domain. Raw scores within `1e-12` are ties; the leftmost placement wins, then
the plus strand. The reported candidate score is the hard minimum across
motifs.

For `relative_pwm_attainment_v2`, the reference-domain endpoints are the sums
of the position-wise minimum and maximum log odds over one motif-width word.
Those word-level extrema are exact. Because candidate evaluation retains the
best score across all valid placements and strands, the sequence-level lower
endpoint need not be reachable when multiple placements or orientations
compete; the upper endpoint remains reachable by embedding a score-maximizing
word.

For a tractable sequence space, search evaluates every sequence. Larger spaces
use a versioned, bounded multi-start annealed stochastic local search. Starts
share one seeded origin and receive deterministic perturbations. The engine
mixes four-base single-position resampling, contiguous-block replacement,
multi-position replacement, motif-guided proposals, and annealed acceptance.
It is not an MCMC sampler, a posterior sampler, or a Gibbs sampler. Proposals
may target the current limiting motif. A smooth minimum guides proposals and a
separate inverse-temperature schedule controls acceptance; neither value is a
public score.

The optimization problem is formulated as max-min: maximize the minimum
target-motif attainment over feasible sequences. Exhaustive search can identify
that maximum when the evaluator budget covers the sequence space. In a larger
space, the heuristic reports the best evaluations observed within its budget,
not a claim that it reached the global max-min solution.

The budget counts calls to the authoritative evaluator, including the four
candidate evaluations used by a single-position resampling move. Equal
evaluator-call budgets do not imply equal compute: per-call work depends on
sequence length, motif number and width, strand policy, and avoiders. Once
evaluated, a sequence and its matches are immutable. Search records bounded
best-score checkpoints, restart-final scores, and proposal counts. Selection
applies deterministic ordering and any declared distance rule to return exactly
the requested portfolio size without constraint relaxation.

The canonical bundle writes the normalized request, motif content, candidate
table, long-form match table, and complete manifest. Publication is atomic and
refuses an existing output path. Replay records package, schema, scoring,
search-engine, RNG, seed, budget, diagnostic, and artifact versions.

This document defines software behavior. Any comparison workflow must
separately define its inputs, controls, repetitions, analysis, acceptance
criteria, and claim boundary.
