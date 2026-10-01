# Reproducibility and result integrity

## Determinism

Within one declared package and runtime environment, the same validated request,
motif content, seed, and budgets produce the same evaluations, selection, and
canonical bytes. JSON is UTF-8, key-sorted, and newline-terminated. Tables use
fixed columns, row ordering, and float formatting. Host paths, usernames, time,
and scheduling do not enter content identity.

CI tests supported Linux and macOS runtimes. Exact byte identity between runtimes
requires a direct comparison; passing their tests alone does not establish it.
`build_lock_sha256` identifies the build's dependency lock, not a consumer's
installed environment. [Attested execution](docs/reference/execution-receipts.md)
records the exact wheel and runtime separately from bundle identity.

## Bounded execution

[Request validation](docs/design-spec.md#combined-resource-bounds) limits
allocation and work before search. Every evaluator call counts. A run records
bounded or exhaustive completion; random sampling remains bounded even when its
allowance could cover the sequence space. Requested count and separation are hard
postconditions. Infeasibility publishes no partial successful bundle.

Single-output search retains the best 256 complete evaluations plus bounded
sequence-discovery identities. Multi-output search keeps its evaluated pool for
constrained selection. Raising the budget can increase memory use even when
complete-evaluation retention is capped. Observation and replay are separate work.
[Search observations](docs/reference/search-observations.md) declare their own
snapshot, quality-sample, base, and byte limits without changing search decisions.

## Artifact integrity

The manifest binds normalized relative paths, byte counts, and SHA-256 digests.
Verification rejects missing, changed, unlisted, symlinked, unsafe, or schema-
invalid members. It parses one descriptor-bound, bounded byte snapshot and replays
scores and selected sites. [Security](SECURITY.md) details untrusted-input handling.

Publication verifies a sibling temporary directory, uses a no-replace atomic
rename, then performs a complete semantic reread from the published destination.
A failed post-publication check is not accepted as a result. Its destination is
left for explicit inspection: concurrent same-user substitution makes automatic
cleanup of that pathname unsafe. Existing output paths are never merged,
replaced, or repaired. Verify results again when consuming them; integrity checks
are not access controls against later tampering.

Manifests have a 64 MiB transport ceiling. Model and specification inputs have
1 MB limits. Admission estimates manifest size before search, and publication
independently checks actual serialized bytes. Byte bounds do not replace schema,
row-count, or score checks.

## Inspection and failures

Inspection accepts one verified result. It keeps derived text, JSON, SVG, and
HTML outside the canonical bundle. Rendered candidates, sites, motifs, and
checkpoints are bounded while their displayed and total counts remain explicit.
Exact distance summaries report `not_computed_limit` when their work limit would
be exceeded. Views do not recompute scientific state.

Unknown schemas or score rules, corrupt models, incomplete inventories, and
unavailable requested counts fail explicitly. FASTA remains a verified bundle
member. [Supported formats](docs/reference/public-contract.md#artifacts) and
[release verification](docs/reference/prerelease.md) specify the remaining
compatibility and distribution requirements.
