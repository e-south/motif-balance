# Reproduce the exact software environment

The canonical bundle is deterministic scientific output. Runtime facts such as
Python, operating system, architecture, installed dependency versions, and wall
clock time do not enter its identity. An atomic
`motif-balance.execution-workspace/v1` retains the resolved input, exact release
wheel, verified bundle, and `motif-balance.execution-receipt/v1`. The receipt
binds the execution interval and runtime facts to the bundle manifest, producer
revision, package-tree digest, search engine, and evaluation counts.

Install the exact release wheel into the active environment first, and retain
that wheel. Replace the wheel path and producer commit below with its release
identities. Create the workspace in the same operation that performs the design:

```bash
# Run the request and check that the installed package matches its release wheel.
motif-balance orchestration execute design.yaml \
  --release-artifact /path/to/motif_balance-VERSION-py3-none-any.whl \
  --producer-revision <40-character-commit> \
  --out execution-workspace
```

The command accepts wheels only. Before and after search it compares every file
in the wheel's `motif_balance` package tree with the running package tree and
fails on any difference. Wheel inspection is bounded, permits only the package
and its declared distribution metadata, and validates every `RECORD` digest.

It publishes through a temporary sibling directory, self-verifies the completed
workspace, and refuses an existing destination.

Attestation proves which
package bytes ran. The producer revision remains an externally supplied release
identity and must be checked against the release record; it is not
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
```

Verification requires four values from an authority outside the object being
checked: workspace ID, receipt digest, release digest, and producer revision.

```bash
# Verify the saved execution against the identities retained from its producer.
motif-balance inspect execution-workspace --source execution \
  --expected-workspace-id <execution-id> \
  --expected-receipt-sha256 <sha256> \
  --expected-release-sha256 <sha256> \
  --expected-producer-revision <40-character-commit>
```

## Retain the workspace without changing its inventory

Storage location, backup, and retention are caller responsibilities. Preserve
the complete execution workspace and its exact members. Keep any external
storage metadata, caches, analysis, or manuscript files outside that root;
adding them inside would invalidate its closed inventory.

Apply the storage provider's checks separately, then inspect the product
workspace with all four external identities above. Storage validation does not
replace product verification, and product verification does not establish backup
adequacy or scientific acceptance. Caller-owned passive search observations
remain separate artifacts, not extra members of the workspace or bundle.

## Supported schemas

The current reader verifies `run-manifest/v7`,
execution receipt v1, and execution workspace v1. Unknown schemas fail explicitly;
the [public contract](public-contract.md#artifacts) owns the supported read/write
matrix. Retain the exact wheel: a package version alone does not identify the
bytes that ran. Retired formats require their original software; there is no
compatibility reader or automatic migration.
