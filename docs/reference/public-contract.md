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

- `MotifModel`
- `DesignSpec`
- `MotifMatch`
- `Evaluation`
- `Candidate`
- `Portfolio`
- `design(spec) -> Portfolio`
- `score(...)`

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

## Artifacts

The canonical integration seam is a verified bundle containing `design.json`,
`motifs.json`, `candidates.tsv`, `matches.tsv`, and `manifest.json`. Consumers
must verify the manifest before reading result tables and should pass a
previously trusted `expected_bundle_id` when crossing an authority boundary.
Verification binds all manifest provenance, recompiles the problem and run
identities, and replays every candidate's authoritative matches and scores.
It does not rerun the search trajectory: evaluation counts and search
provenance remain producer-declared metadata whose authenticity depends on the
externally trusted bundle identity. A study making execution claims must rerun
the pinned release and retain a separate execution receipt.

Research Studies may register verified outputs as evidence. `manufold` may
snapshot an accepted minimal artifact by digest. Neither consumer should import
Motif Balance internals, follow a live output directory, or treat a package
version as evidence acceptance.
