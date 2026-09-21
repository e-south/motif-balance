---
doc_id: motif-balance-architecture
title: Motif Balance architecture
intent: Define module responsibilities and dependency direction.
audience: [maintainers]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-20
doc_type: explanation
journey: [maintain]
---

# Motif Balance architecture

The package separates interpreting motif models, scoring DNA, proposing edits,
choosing candidates and presenting results. Each stage has one implementation
responsible for its scientific meaning. The [module map](docs/reference/module-map.md)
locates those implementations and their allowed imports.

## Data flow

```text
DesignSpec → compile → evaluate → search → select → Portfolio → result bundle
```

Compilation validates the request and prepares log-odds matrices. Scoring returns
immutable sequence evaluations. Search proposes more sequences; selection chooses
among completed evaluations. Neither changes an evaluation after scoring.
Inspection verifies saved results before projecting them into figures or tables.

## Dependency direction

Models and constants have no dependency on search, files or rendering. Formats,
compilation and scoring sit above them. Search and selection use the evaluator;
the API coordinates these operations. Artifact handling saves and replays their
records. Inspection and the CLI use those interfaces instead of reimplementing
the method.

Renderers consume validated projections. They do not search, rescore, fetch
models or read result directories. This lets a new output format reuse the same
scoring and verification behavior.

The architecture check in `scripts/check_architecture.py` checks imports,
including relative imports, and rejects unknown modules. New responsibilities
need an explicit place in the [module map](docs/reference/module-map.md) and
matching checks.

## Integration boundary

The package accepts explicit inputs and produces versioned results. It has no
runtime dependency on another repository. Data acquisition, study design,
comparison across runs and manuscript composition belong in the consuming
project. Share released software and result artifacts rather than importing
another checkout's source files.

See [information architecture](IA.md) for terminology and artifact routing,
[design contracts](DESIGN.md) for invariants, and [Contributing](CONTRIBUTING.md)
for the development workflow.
