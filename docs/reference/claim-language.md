---
doc_id: motif-balance-claim-language
title: Claim-language check
intent: Define the bounded advisory wording check for downstream study and manuscript text.
audience:
  - study authors
  - manuscript authors
  - maintainers
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-31
doc_type: reference
journey:
  - integrate
---

# Claim-language check

`motif_balance.claim_language.check_claim_text(text)` deterministically reports
a small set of wording hazards known to matter when Motif Balance results are
used in studies or manuscripts. It is an intentional advanced submodule seam,
not a top-level API or CLI command.

Each immutable `ClaimFinding` gives a stable rule ID, severity, one-based source
line, exact matched text, rationale, and safer wording. The current rules cover:

- broad first or novelty claims contradicted by established motif and inverse-
  design prior art;
- confusion between theoretical single-site score extrema and the attainable
  range of a sequence after best-window scanning;
- global-optimality or convergence language without exhaustive evidence;
- affinity, binding, occupancy, or expression claims from uncalibrated PWM
  scores; and
- physical interpretations of model-defined overlap or compatibility.

Common match-adjacent explicit nonclaims, genuine prior-art discussion,
complete-sequence-space exhaustive context, claimant-qualified affinity
calibration, and model-defined sequence-score terminology are excluded to
reduce predictable false positives.

The rule set is bounded, advisory, and necessarily incomplete. The checker
neither rewrites text nor decides whether a claim is supported. A clean result
means only that no configured wording hazard was found. It does not establish
evidence quality, literature completeness, claim acceptance, or publication
readiness. Research Studies owns evidence and claim decisions; `manufold` owns
manuscript composition. Because its coverage is deliberately bounded, the
checker may still flag quoted prohibited examples that lack adjacent review
language.
