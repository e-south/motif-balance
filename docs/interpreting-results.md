---
doc_id: motif-balance-interpreting-results
title: Interpreting Motif Balance results
intent: Explain result fields, comparison limits, and appropriate claims.
audience:
  - users
  - bundle consumers
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-26
doc_type: how-to
journey:
  - verify
---

# Interpreting Motif Balance results

Start with `manifest.json` and verify the bundle before using any table. Then
read results at three levels:

1. `candidates.tsv` contains one immutable row per selected sequence, including
   its public balance score and deterministic rank.
2. `matches.tsv` contains one row per candidate and motif, including the chosen
   span, strand, oriented matched sequence, raw score, and normalized score.
3. `design.json` and `motifs.json` state the request and model content against
   which those values are meaningful.

The lowest per-motif normalized value determines a candidate's balance score.
Inspect that limiting motif rather than treating the aggregate as a generic
quality probability. A difference is meaningful only under the same motif
content, score version, strand rule, and normalization authority.

Do not claim measured binding, expression, fitness, biological portability, or
superiority to a baseline from these artifacts alone. Those conclusions require
a study-owned comparison design and evidence record. Search completion and
portfolio diversity are also distinct from motif score quality.

`manifest.json` also contains bounded search diagnostics. Best-score
checkpoints show computational progress, restart-final scores show between-start
variation, and proposal summaries describe execution. They are optimizer
diagnostics, not posterior samples, convergence statistics, or biological
replicates.
