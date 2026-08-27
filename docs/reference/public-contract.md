---
doc_id: motif-balance-public-contract
title: Motif Balance public contract
intent: Define the supported API, CLI, and artifact integration seams.
audience:
  - API consumers
  - integrators
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-26
doc_type: reference
journey:
  - integrate
---

# Motif Balance public contract

## Python

Import supported contracts and operations only from `motif_balance`:

- Data contracts: `MotifModel`, `DesignSpec`, `MotifMatch`, `Evaluation`,
  `Candidate`, and `Portfolio`.
- Error contracts: `MotifBalanceError`, `InvalidMotif`, `InvalidDesign`,
  `InvalidSequence`, `IncompatibleDesign`, `SearchExhausted`, and
  `ArtifactError`.
- Scientific operations: `compile_spec`, `design`, and `score`.
- Input operations: `read_motif`, `convert_motif`, and `load_spec`.
- Artifact operations: `read_portfolio`, `verify_bundle`,
  `render_bundle_report`, `execute_design_workspace`, and
  `verify_execution_workspace`.
- Inspection operations: `inspect_result`, `build_result_catalog`,
  `summarize_inspection`, `render_inspection_html`, and
  `render_result_catalog_html`.

`score(sequence, spec) -> Evaluation` returns the authoritative immutable match
and scoring record for one sequence.

`design(spec) -> Portfolio` either returns exactly `spec.count` candidates or
raises the top-level `SearchExhausted` contract. Its structured fields record
the requested and valid counts, evaluations used, best observed score, and the
limiting condition. Consumers must not parse exception prose or import
`motif_balance.errors` as a compatibility seam.

`Portfolio.write(path)` is the supported convenience for publishing a canonical
bundle. The public facade owns that orchestration even if its implementation is
kept outside the lower model layer. Internal modules and functions are not
compatibility seams.

## Command line

The supported executable is `motif-balance`. Scientific meaning comes from a
strict serialized `DesignSpec`; file destinations and verification behavior are
operational options. Command help is part of the clean-install smoke test.

- `design SPEC --check` compiles and explains the planned search mode.
- `design SPEC --out DIR` executes and atomically publishes a bundle.
- `verify DIR` verifies bytes, schemas, identities, and scientific replay.
- `render-report DIR --out FILE` regenerates HTML from a verified bundle and
  requires the new file to remain outside that bundle.
- `convert-motif FILE ...` performs an explicit JASPAR conversion.
- `execute SPEC --release-artifact WHEEL ...` attests the running package tree
  against the wheel and atomically publishes an execution workspace.
- `verify-execution DIR ...` verifies that workspace against externally trusted
  workspace, receipt, release, and revision identities.
- `inspect DIR --kind ...` verifies and explains one explicitly typed result.
- `catalog --entry ID=KIND:PATH ...` joins explicit inspections into a derived
  portable catalog without directory discovery.

Default errors have stable codes, optional field or motif context, and a
corrective hint. Raw validation internals and stack traces require `--debug`.

## Artifacts

The canonical integration seam is a verified bundle containing `design.json`,
`motifs.json`, `candidates.tsv`, `matches.tsv`, and `manifest.json`. Consumers
must verify the manifest before reading result tables and should pass a
previously trusted `expected_bundle_id` when crossing an authority boundary.
Verification binds all manifest provenance, recompiles the problem and run
identities, and replays every candidate's authoritative matches and scores.
It does not rerun the search trajectory: evaluation counts and search
provenance remain producer-declared metadata. A workflow relying on execution
identity must use the pinned release through `execute` and retain the complete
execution workspace, not add a receipt to an independently produced bundle.

Version `0.2` accepts `run-manifest/v2` only. It does not reinterpret or
silently upgrade `run-manifest/v1`. Scientific replay pins the package wheel,
producer revision, runtime contract, build lock, search engine name and engine
version. Supporting another manifest generation requires an explicit version
dispatcher and compatibility tests.

See [execution receipts](execution-receipts.md) for the runtime and storage
boundary.

See [result inspection](result-inspection.md) for trust-state and bounded-view
semantics. Inspection and catalogs accept current product artifacts only;
neither is a canonical bundle or evidence-acceptance record.

Consumers should use immutable artifacts and digests, not import internals or
follow a live output directory. Package verification establishes product
integrity, not downstream acceptance.
