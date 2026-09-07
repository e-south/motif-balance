---
doc_id: motif-balance-methods
title: Motif Balance methods
intent: State the software method precisely enough for replay and review.
audience:
  - users
  - integrators
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-06
doc_type: reference
---

# Motif Balance methods

For each candidate sequence, Motif Balance enumerates valid placements for each
declared motif and strand. It scores each placement through the versioned
scoring authority, selects one best match with a deterministic total-order tie
break, and normalizes the selected score using the model's declared reference
domain. Raw scores within `1e-12` are ties; the leftmost placement wins, then
the plus strand. Each motif is scanned once. A seek specification uses the
normalized attainment directly; an avoid specification uses one minus that
attainment. The reported candidate score is the hard minimum across these
directional satisfactions. Avoidance is model-relative and does not establish
biological absence.

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
It is a bounded optimizer, not a probabilistic sampler. Proposals
may target the current limiting motif. A smooth minimum guides proposals and a
separate inverse-temperature schedule controls acceptance; neither value is a
public score.

The directional optimization problem is formulated as max-min: maximize the
minimum seek-or-avoid specification satisfaction. Exhaustive search can identify
that maximum when the evaluator budget covers the sequence space. In a larger
space, the heuristic reports the best evaluations observed within its budget,
not a claim that it reached the global max-min solution.

The budget counts calls to the authoritative evaluator, including the four
candidate evaluations used by a single-position resampling move. Equal
evaluator-call budgets do not imply equal compute: per-call work depends on
sequence length, motif number and width, strand policy, and avoiders. Once
evaluated, a sequence and its matches are immutable. Directional search records
logarithmic best-score checkpoints with retained per-specification satisfactions
and the limiting specification, restart-final scores, proposal counts, and at
most 256 deterministic score-ranked unique elites. Complete proposal histories
are not written. Selection applies deterministic ordering and any declared
distance rule to return exactly the requested portfolio size without constraint
relaxation.

The canonical bundle writes the normalized request, motif content, candidate
table, long-form match table, and complete manifest. Publication is atomic and
refuses an existing output path. Replay records package, schema, scoring,
search-engine, RNG, seed, budget, diagnostic, exact-or-bounded completion,
elite, and artifact versions.

This document defines software behavior. Any comparison workflow must
separately define its inputs, controls, repetitions, analysis, acceptance
criteria, and claim boundary.
