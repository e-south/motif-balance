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
---

# Motif Balance public contract

## Python

Import supported contracts and operations only from `motif_balance`:

- Data contracts: `MotifModel`, `DesignSpec`, `MotifMatch`, `Evaluation`,
  `Candidate`, and `Portfolio`.
- Scientific operations: `compile_spec`, `design`, and `score`.
- Input operations: `read_motif`, `convert_motif`, and `load_spec`.
- Artifact operations: `read_portfolio`, `verify_bundle`,
  `render_bundle_report`, `execute_design_workspace`, and
  `verify_execution_workspace`.

`score(sequence, spec) -> Evaluation` returns the authoritative immutable match
and scoring record for one sequence.

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
- `render-report DIR --out FILE` regenerates HTML from a verified bundle.
- `convert-motif FILE ...` performs an explicit JASPAR conversion.
- `execute SPEC --release-artifact WHEEL ...` attests the running package tree
  against the wheel and atomically publishes an execution workspace.
- `verify-execution DIR ...` verifies that workspace against externally trusted
  workspace, receipt, release, and revision identities.

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
provenance remain producer-declared metadata. A study making execution claims
must use the pinned release through `execute` and retain the complete execution
workspace, not add a receipt to an independently produced bundle.

Version `0.2` accepts `run-manifest/v2` only. It does not reinterpret or
silently upgrade `run-manifest/v1`. Scientific replay pins the package wheel,
producer revision, runtime contract, build lock, search engine name and engine
version. Supporting another manifest generation requires an explicit version
dispatcher and compatibility tests.

See [execution receipts](execution-receipts.md) for the runtime and storage
boundary.

Research Studies may register verified outputs as evidence. `manufold` may
snapshot an accepted minimal artifact by digest. Neither consumer should import
Motif Balance internals, follow a live output directory, or treat a package
version as evidence acceptance.
