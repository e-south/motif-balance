---
doc_id: motif-balance-reliability
title: Motif Balance reliability contract
intent: Define determinism, bounded execution, artifact integrity, and degraded behavior.
audience:
  - maintainers
  - bundle consumers
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-29
doc_type: reference
---

# Motif Balance reliability contract

## Determinism

The same normalized specification, motif content, scoring version, package
version, seed, and budgets must produce the same evaluated records, selection,
and canonical artifact bytes. Canonical JSON is UTF-8, key-sorted, human-readable, and
ends with one newline. Tables have fixed columns, stable row order, explicit
float formatting, and one trailing newline. Host paths, usernames, timestamps,
thread completion order, and environment mapping order do not enter content
identity.

That same-byte claim is release-gated on the hosted Linux CPython 3.12-3.14
matrix. Local macOS checks establish alpha operability, but the project does not
claim cross-host byte identity beyond the published release evidence.

`build_lock_sha256` identifies the repository lock used to build this alpha;
it is not a claim that a wheel consumer installed that exact environment.
Runtime versions are deliberately excluded from canonical bundle identity and
belong in an attested execution workspace when a caller needs them.

## Bounded execution

Every search has explicit evaluation and candidate budgets. Specification
validation also bounds evaluated bases, score operations, and positive-distance
comparisons before compilation. A successful
result records whether it exhausted the full sequence space or the declared
budget. A budget-limited result is never represented as exhaustive. An
infeasible request raises a typed failure and publishes no partial bundle or
completed execution workspace. Workflows measuring failure rates must record
their trial outcome separately. The requested output count and diversity
constraints are hard postconditions.

Hard avoider ceilings are feasibility constraints, not score penalties.
Complete enumeration may report an exact infeasibility proof. A heuristic run
that finds too few feasible sequences reports budget exhaustion without
generalizing beyond its evaluated pool. Portfolio infeasibility and the
distance-selection node limit remain separate outcomes.

The public specification also caps sequence length, candidate count, evaluator
calls, total portfolio bases, and canonical match rows. Sequence-space
classification stops once the declared bound is exceeded; it never computes
an arbitrarily large exponent or allocates a sequence-space-sized collection.
The compiled null expectation uses linearity of expectation over motif
positions; it does not materialize the combinatorial null-score distribution.

## Artifact integrity

`manifest.json` inventories every other bundle artifact with a normalized
relative path, byte count, and SHA-256 digest. Verification rejects
missing, symlinked, modified, unmanifested, path-traversing, or schema-invalid
content. Verification parses and replays one descriptor-bound, bounded byte
snapshot; it does not reread member paths after verification. JSON, bundle
bytes, and semantic table rows have explicit pre-read or streaming bounds.
Bundle publication writes to a sibling temporary directory, verifies
the complete result, and renames it atomically. Existing output paths are never
merged, replaced, or partially repaired.

Bulk traces and optimizer state are not canonical bundle members. External
systems may register their locations and digests without changing the software
artifact identity.

Result inspections are derived after verification and are never inserted into
`run-manifest/v2`, `run-manifest/v3`, `run-manifest/v4`, or `run-manifest/v5`. Inspection accepts one explicit result;
cross-result joining remains a caller responsibility. Exact
pairwise distance inspection has an explicit base-comparison limit and reports
`not_computed_limit` instead of entering unbounded quadratic work. HTML and SVG
views bound rendered candidates, matches, motifs, and checkpoints while
preserving exact displayed and total counts. Wide SVGs keep explicit dimensions
and are horizontally scrollable rather than illegibly compressed. Print output
uses a bounded print-only copy of progressively disclosed tables because
Chromium does not print descendants of closed `details` elements.

Evaluated-pool observations are separate bounded JSON exports. They contain at
most 32,768 unique evaluations and 64 MiB, refuse overwrite, use a
descriptor-bound no-symlink reader, bind their content identity, and replay
every score before publication and after reading. The advanced paired design
operation performs one exploratory search; independent pool publication and
reading continue to replay that search at their trust boundaries.

## Degraded behavior

There is no permissive fallback for an unknown schema, scoring version, strand
rule, corrupted motif model, incomplete artifact inventory, or unavailable
candidate count. Derived FASTA is a verified bundle member. On-demand text,
JSON, SVG, and HTML reviews are not bundle members or scientific authorities;
they may not recompute candidate or match state.
