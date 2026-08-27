---
doc_id: motif-balance-execution-receipts
title: Execution workspace and storage object contract
intent: Define attested runtime provenance and durable dogfood object boundaries.
audience:
  - integrators
  - evidence producers
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-26
doc_type: reference
---

# Execution workspace and storage object contract

The canonical bundle is deterministic scientific output. Runtime facts such as
Python, operating system, architecture, installed dependency versions, and wall
clock time do not enter its identity. An atomic
`motif-balance.execution-workspace/v1` retains the resolved input, exact release
wheel, verified bundle, and `motif-balance.execution-receipt/v1`. The receipt
binds the execution interval and runtime facts to the bundle manifest, producer
revision, package-tree digest, search engine, and evaluation counts.

Create the workspace in the same operation that performs the design:

```bash
motif-balance execute design.yaml \
  --release-artifact dist/motif_balance-0.2.0a1-py3-none-any.whl \
  --producer-revision <40-character-commit> \
  --out execution-workspace
```

The command accepts wheels only. Before and after search it compares every file
in the wheel's `motif_balance` package tree with the running package tree and
fails on any difference. Wheel inspection is bounded, permits only the package
and its declared distribution metadata, and validates every `RECORD` digest.
It publishes through a temporary sibling directory, self-verifies the completed
workspace, and refuses an existing destination. Attestation proves which
package bytes ran. The producer revision remains an externally supplied release
identity and must be checked against the private release record; it is not
derived from the wheel. Attestation does not certify downstream acceptance or
comparison quality.

The workspace contains:

```text
execution-workspace.json
execution-receipt.json
inputs/
  design-spec.json
  motif_balance-<version>-<tags>.whl
  SHA256SUMS
bundle/
  design.json
  motifs.json
  candidates.tsv
  matches.tsv
  manifest.json
  candidates.fasta
  report.html
```

Verification requires four values from an authority outside the object being
checked: workspace ID, receipt digest, release digest, and producer revision.

```bash
motif-balance verify-execution execution-workspace \
  --expected-workspace-id <execution-id> \
  --expected-receipt-sha256 <sha256> \
  --expected-release-sha256 <sha256> \
  --expected-producer-revision <40-character-commit>
```

## Durable dogfood object

Storage may retain the product directory inside
`workspaces/motif-balance/<storage-id>/workspace/`. The containing Storage
object owns `storage.object.json`; the nested product root preserves Motif
Balance's exact inventory. The envelope uses separate fields:

```json
{
  "content_schema": "motif-balance.execution-workspace",
  "content_schema_version": "1",
  "object_kind": "workspace",
  "owner_repository": "motif-balance",
  "owner_tool": "motif-balance"
}
```

The logical content is:

```text
storage.object.json
workspace/
  execution-workspace.json
  execution-receipt.json
  inputs/
  bundle/
```

The storage object manifest owns placement, retention, resource inventory, and
object closure. The execution index owns the product workspace inventory. The
bundle manifest remains the authority for scientific result content. No
manifest replaces another owner's contract.

Run Storage validation against the envelope root and
`motif-balance verify-execution` against the nested `workspace/`. Adding the
Storage envelope to the product root is invalid because both contracts close
their own inventories.

Do not copy in caches, optimizer traces, comparison decisions, or presentation
prose. Bulk traces, if explicitly enabled outside the product path, require a
separate typed resource and must not be inserted into this execution workspace
or the canonical bundle.

## Supported schemas

Motif Balance `0.2` verifies `run-manifest/v2`, execution receipt v1, and
execution workspace v1. It rejects earlier or unknown schemas. Retain the exact
wheel because scientific replay is exact-build replay; a package version alone
is not enough. Future compatibility must be implemented as an explicit schema
dispatcher with tests, never as permissive parsing.
