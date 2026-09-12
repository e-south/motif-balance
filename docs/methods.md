---
doc_id: motif-balance-methods
title: Motif Balance methods
intent: State the software method precisely enough for replay and review.
audience:
  - users
  - integrators
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-07
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

By default, a tractable sequence space is enumerated completely. Larger spaces
use a versioned, bounded multi-start annealed stochastic local search. Starts
share one seeded origin and receive deterministic perturbations. The engine
mixes four-base single-position resampling, contiguous-block replacement,
multi-position replacement, motif-guided proposals, and annealed acceptance.
It is a bounded optimizer, not a probabilistic sampler. Proposals
may target the current limiting motif. A smooth minimum guides proposals and a
separate inverse-temperature schedule controls acceptance; neither value is a
public score.

The default initialization is `related`. Directional Python requests can
explicitly select `independent`: every start is a fresh uniform DNA draw,
with no uniqueness or distance constraint. Its engine identity is
`annealed_independent_starts_v1`; the moves, schedule, scoring, selection, and
evaluator budget are otherwise the same. The option is a method-comparison
surface, not evidence of superior recovery. Exact enumeration ignores
initialization because it visits the complete admitted sequence space.

## Explicit comparison methods

Directional Python calls accept `method="annealed"` (the default), `"greedy"`,
or `"random"`. `design_observed` accepts the same option. All use the same
compiled evaluator, score ordering, elite capacity, selection, and optional
quality-sample retention. Each invocation prepares scoring inputs once.
Changing method changes the run identity, not the problem identity. The CLI
continues to use the default; method comparison does not happen automatically.

Greedy search uses eight starts and the same `related` or `independent`
initialization as annealed search. It visits chains in turn, chooses one random
coordinate, and scores its A/C/G/T substitutions in that order, including the
unchanged base. It adopts only a strict hard-minimum improvement; improving
ties choose the lexical sequence. Neutral trials retain the current state.
It does not restart on stagnation or traverse neutral plateaus. A remaining
budget of one to three calls evaluates only that many substitutions; every
scored proposal remains eligible for retention. These are explicit limitations
of a simple control, not evidence that annealing is better. Engines are
`greedy_multistart_v1` and `greedy_independent_starts_v1`.

Random sampling (`uniform_random_v1`) draws one independent whole DNA sequence
per call using PCG64, uniform A/C/G/T choices, and int8 vector draws. Sampling is
with replacement: repeated sequences consume calls but are not new discoveries.
There are no local moves or chain initialization; omit `initialization`.
Nondefault initialization is rejected rather than ignored. Random requests
never switch to enumeration, even when their budget exceeds `4^length`; they
remain `budget_exhausted`, not an exact-optimum claim. The single diagnostic
stream reports its retained best and observations have no chain states.

Annealed and greedy requests still enumerate when the budget covers the whole
space. Both then record `exhaustive_v1`. A comparison must check the recorded
engine rather than assume the requested label identifies the executed method.
Greedy and random options require directional v3 requests; no legacy fallback
is provided.

## Budget, retention, and interpretation

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

The in-memory ledger still retains all unique evaluations for selection and
exact discovery accounting. The elite export limit is not a working-memory
bound. Repeated calls, unique discoveries, retained elites, selected candidates,
and reverse-complement equivalence classes are different counts. Benchmark
preparation, search, selection, observation/replay, and publication separately;
equal calls alone do not establish equal wall time or memory.

The canonical bundle writes the normalized request, motif content, candidate
table, long-form match table, and complete manifest. Publication is atomic and
refuses an existing output path. Replay records package, schema, scoring,
search-engine, RNG, seed, budget, diagnostic, exact-or-bounded completion,
elite, and artifact versions.

This document defines software behavior. Any comparison workflow must
separately define its inputs, controls, repetitions, analysis, acceptance
criteria, and claim boundary.
