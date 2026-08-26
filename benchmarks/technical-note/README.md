---
doc_id: motif-balance-technical-note-fixtures
title: Technical-note validation fixtures
intent: Route maintainers to sanitized scoring and production-search regression records.
audience:
  - maintainers
  - evidence producers
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-26
doc_type: reference
---

# Technical-note validation fixtures

This directory contains sanitized migration fixtures, not accepted scientific evidence. The
`scoring-parity-v1.json` record pins the smallest Cruncher Sample scoring comparison used to
classify the standalone contract. Research Studies owns evidence acceptance and manuscript claim
gates.

`scoring-parity-v1.json` classifies the deterministic scoring comparison.
`search-validation-v1.json` freezes the new production engine under the canonical
Motif Balance semantics. It is a product regression record, not comparative
performance evidence. Cross-implementation optimizer results remain
study-owned because proposal accounting and corrected final-candidate semantics
are intentionally different.
