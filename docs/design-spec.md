---
doc_id: motif-balance-design-spec
title: Design specification reference
intent: Describe immutable scientific inputs and operational boundaries.
audience:
  - API consumers
  - CLI users
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-26
doc_type: reference
---

# Design specification reference

`DesignSpec` is the complete scientific request. It declares at least the motif
models or their content-bound references, exact sequence length, requested
candidate count, strand policy, search seed and budgets, and any minimum
distance constraint. Unknown fields fail instead of being ignored.

Scientific settings live in the specification so the same serialized request
has the same meaning through Python and the CLI. Operational options such as an
output directory, log verbosity, or whether to verify an already written
bundle are not scientific inputs and do not alter its digest.

A valid request does not guarantee feasibility. Motif length, candidate count,
search bounds, and diversity constraints are validated explicitly. The design
operation returns exactly the requested count or reports a typed failure; it
does not relax constraints or silently return fewer candidates.

## Resource limits

`design-spec/v1` has explicit implementation limits. `length` is at most
10,000 bases, `count` at most 100,000 candidates, and `evaluations` at most
1,000,000 evaluator calls. In addition, a request may describe at most
1,000,000 canonical candidate-motif match rows and 10,000,000 total portfolio
bases. The evaluator budget must be at least the requested count.

These limits are validation rules, not search heuristics. Requests outside
them fail before compilation or search. Complete-space checks use bounded
multiplication and never construct an unbounded `4**length` integer.

See [engineering contracts](../DESIGN.md) for the invariants and
[reliability](../RELIABILITY.md) for deterministic serialization.
