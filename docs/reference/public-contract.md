---
doc_id: motif-balance-public-contract
title: Motif Balance public contract
intent: Define the supported scientific API, ordinary CLI, and artifact seam.
audience:
  - API consumers
  - integrators
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-27
doc_type: reference
journey:
  - integrate
---

# Motif Balance public contract

## Python

The top-level facade has five nouns and two verbs:

```python
from motif_balance import (
    MotifModel,
    DesignSpec,
    MotifMatch,
    Candidate,
    Portfolio,
    design,
    score,
)
```

`score(sequence, spec)` returns the authoritative immutable evaluation for one
sequence. `design(spec)` returns exactly `spec.count` ranked candidates or
raises a typed error. `Portfolio.write(path)` atomically publishes a new result
bundle. Inputs and public models are strict and immutable.

Serialized numeric fields must be native YAML or JSON numbers; quoted numeric
strings are rejected. One advanced review contract is intentional:

```python
from motif_balance.inspection import ResultInspection, inspect_result
```

Renderers, conversion helpers, bundle readers, and execution attestation remain
deliberate submodule or CLI surfaces. They are absent from the top-level
scientific facade and may evolve with their versioned artifact schemas.

## Command line

The ordinary command help exposes three journeys:

```text
design   validate or execute a DesignSpec
score    evaluate one supplied sequence
inspect  verify and review one immutable result
```

`inspect` automatically verifies bytes, schemas, identities, and score replay.
It emits text by default and can export inspection JSON or one candidate,
portfolio, or search-record SVG. HTML is the optional linear composition of
those same renderers.

Advanced integration commands are intentionally hidden from ordinary help:

```text
motif-balance motif prepare ...
motif-balance orchestration execute ...
```

Motif preparation converts one explicitly supplied supported source. It does
not discover or fetch databases. Orchestration binds an execution to an exact
wheel and producer revision. Neither operation adds a new scientific verb.

## Artifacts

The immutable result seam is:

```text
design.json
motifs.json
candidates.tsv
matches.tsv
manifest.json
candidates.fasta  # derived, manifest-bound
```

The manifest binds every other member by relative path, size, and SHA-256.
Verification recompiles the problem and replays each published candidate's
matches and hard-minimum score. It does not rerun search. Text, inspection
JSON, SVG, and HTML are regenerable projections outside the bundle.

Version `0.3` reads `run-manifest/v2`, `run-manifest/v3`, and
`motif-balance.result-inspection/v2`. Unknown schemas fail closed. A workflow
that needs exact runtime identity retains the complete
`motif-balance.execution-workspace/v1` with its wheel and external trust
anchors.

Package verification establishes product integrity. It does not accept a
scientific claim, define a benchmark cohort, or confer manuscript status.
