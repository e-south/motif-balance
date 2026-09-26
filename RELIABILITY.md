---
doc_id: motif-balance-reliability
title: Motif Balance reliability contract
intent: Define determinism, bounded execution, artifact integrity, and degraded behavior.
audience: [maintainers, bundle consumers]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-20
doc_type: reference
---

# Motif Balance reliability contract

## Determinism

Within one declared package and runtime environment, the same validated
specification, motif content, scoring version, seed, and budgets must produce
the same evaluated records, selection, and canonical artifact bytes. Canonical
JSON is UTF-8, key-sorted, human-readable, and ends with one newline. Tables
have fixed columns, stable row order, explicit float formatting, and one
trailing newline. Host paths, usernames, timestamps, thread completion order,
and environment mapping order do not enter content identity.

Hosted CI verifies behavior on Linux with CPython 3.12-3.14, but it does not
currently compare artifact digests across that matrix. Local checks cover macOS.
Reproducing exact bytes across runtimes therefore requires a direct comparison
of those environments.

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

An explicit random method samples with replacement and reports bounded
completion even if its budget could cover the entire space. All methods count
every evaluator call and track exact sequence discovery identities. For a
single requested output, full evaluation retention is bounded to the exact top
256 unique candidates; search states, the selected winner, exported elites and
passive observations are unchanged. Multi-output requests retain their complete
evaluated pool for constrained selection. The discovery index still grows with
unique sequences within the evaluation/base limits, so profile process peak
memory when raising an experiment's budget. Single-output requests admit up to
two billion score operations; multi-output requests retain the 100-million
limit. Observation/replay is separate work, not part of the search-call budget.

Avoidance contributes a directional satisfaction to the objective; it is not
a hard exclusion guarantee. Portfolio infeasibility and the distance-selection
node limit remain separate outcomes.

The public specification also caps sequence length, candidate count, evaluator
calls, total portfolio bases, and canonical match rows. Sequence-space
classification stops once the declared bound is exceeded; it never computes
an arbitrarily large exponent or allocates a sequence-space-sized collection.
Compilation computes attainable raw-score extrema directly from motif columns.

## Artifact integrity

`manifest.json` inventories every other bundle artifact with a normalized
relative path, byte count, and SHA-256 digest. Verification rejects
missing, symlinked, modified, unmanifested, path-traversing, or schema-invalid
content. Verification parses and replays one descriptor-bound, bounded byte
snapshot; it does not reread member paths after verification. JSON, bundle
bytes, and semantic table rows have explicit pre-read or streaming bounds.
Bundle publication writes to a sibling temporary directory, verifies
the complete result, and renames it atomically. The publisher pins the source
directory identity through the no-replace rename and then performs a complete
semantic reread and replay from the published destination before returning.
A destination that fails this publish-time check is not accepted as a result.
The failure path deliberately does not rename, delete, quarantine, or otherwise
mutate that destination pathname: under concurrent same-user substitution, no
pathname cleanup can safely prove it still addresses the rejected directory.
The path is left for explicit inspection and owner-directed cleanup. Existing
output paths are never merged, replaced, or partially repaired. These checks
detect mutation during publication; they are not an access-control mechanism
and do not prevent the same user from tampering with accepted files later.
Consumers must verify a bundle or execution workspace again at the point of
use.

Bulk traces and optimizer state are not canonical bundle members. Directional
v7 manifests retain only logarithmic checkpoints and a deterministic reservoir
of at most 256 unique elites. External
systems may register their locations and digests without changing the software
artifact identity.

Directional v7 manifests have a 64 MiB transport ceiling, enforced before reads
and before canonical manifest publication. This accommodates the bounded elite
reservoir's per-specification realizations. Model/specification inputs retain
their 1 MB limits; all schema, row-count, and semantic
replay checks remain independent of the transport ceiling. Before search, v3 admission conservatively projects
manifest bytes from the bounded elite count, specification identifiers and
widths, sequence length, and logarithmic checkpoint count. Requests exceeding
the transport ceiling are refused before evaluation; the actual serialized
byte ceiling remains an independent publication check.

Result inspections are derived after verification and are never inserted into
canonical manifests. Inspection accepts one explicit result;
cross-result joining remains a caller responsibility. Exact
pairwise distance inspection has an explicit base-comparison limit and reports
`not_computed_limit` instead of entering unbounded quadratic work. HTML and SVG
views bound rendered candidates, matches, motifs, and checkpoints while
preserving exact displayed and total counts. Wide SVGs keep explicit dimensions
and are horizontally scrollable rather than illegibly compressed. Print output
uses a bounded print-only copy of progressively disclosed tables because
Chromium does not print descendants of closed `details` elements.

Directional search observations are opt-in, bounded side records, separate
from canonical bundles. Their
[contract](docs/reference/search-observations.md) bounds snapshots, quality
samples, bases, and bytes before search, checks actual serialized size before
return, and replays all observations on reading. Passive retention and
instrumentation do not change the canonical portfolio or evaluator-call budget.

## Failure behavior

Unknown schemas, scoring versions or strand rules, corrupted models, incomplete
artifact inventories and unavailable candidate counts fail explicitly. Derived FASTA is a verified bundle member. On-demand text,
JSON, SVG, and HTML reviews are not bundle members or scientific authorities;
they may not recompute candidate or match state.
