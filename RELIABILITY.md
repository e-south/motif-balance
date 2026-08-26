---
doc_id: motif-balance-reliability
title: Motif Balance reliability contract
intent: Define determinism, bounded execution, artifact integrity, and degraded behavior.
audience:
  - maintainers
  - bundle consumers
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-26
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

`build_lock_sha256` identifies the repository lock used to build this alpha;
it is not a claim that a wheel consumer installed that exact environment.
Runtime versions are deliberately excluded from canonical identity and belong
in an external execution receipt when a downstream study needs them.

## Bounded execution

Every search has explicit evaluation and candidate budgets. A result records
whether the search completed, exhausted a budget, or proved infeasible. A
budget-limited result is never represented as exhaustive. The requested output
count and diversity constraints are hard postconditions.

## Artifact integrity

`manifest.json` inventories every other bundle artifact with a normalized
relative path, byte count, and SHA-256 digest. Verification rejects
missing, symlinked, modified, unmanifested, path-traversing, or schema-invalid
content. JSON, bundle bytes, and semantic table rows have explicit pre-read or
streaming bounds. Bundle publication writes to a sibling temporary directory, verifies
the complete result, and renames it atomically. Existing output paths are never
merged, replaced, or partially repaired.

Bulk traces and optimizer state are not canonical bundle members. External
evidence systems may register their locations and digests without changing the
software artifact identity.

## Degraded behavior

There is no permissive fallback for an unknown schema, scoring version, strand
rule, corrupted motif model, incomplete artifact inventory, or unavailable
candidate count. Derived FASTA and HTML views are verified bundle members but
are not scientific authorities; they may not recompute candidate or match state.
