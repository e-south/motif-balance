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

Search proposes fixed-length sequences under a recorded seed and explicit
evaluation budget. A smooth approximation may guide proposals, but evaluated
records and public ordering use only the hard-min score. Once evaluated, a
candidate is immutable. Selection applies deterministic ordering and any
declared distance rule to return exactly the requested portfolio size.

The canonical bundle writes the normalized request, motif content, candidate
table, long-form match table, and complete manifest. Publication is atomic and
refuses an existing output path. Replay records package, schema, scoring, seed,
and budget versions.

This document defines software behavior. A study must separately define its
task cohort, baselines, repetitions, statistical analysis, evidence acceptance,
and claim boundary.
