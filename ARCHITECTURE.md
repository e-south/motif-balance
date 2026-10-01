# Motif Balance architecture

Motif interpretation, scoring, search, selection, and presentation have separate
owners. The [module map](docs/reference/module-map.md) locates the implementation
and allowed imports for each responsibility.

```text
DesignSpec → compile → evaluate → search → select → Portfolio → result bundle
```

Compilation validates the request and prepares log-odds matrices. Scoring returns
immutable sequence evaluations. Search proposes candidates; selection chooses
among completed evaluations. Inspection verifies saved results before projecting
them into figures or tables.

## Dependency direction

Models and constants have no dependency on search, files, or rendering. Formats,
compilation, and scoring use those definitions. The API coordinates search and
selection; artifact handling saves and verifies their records. Inspection and the
CLI call these interfaces instead of reimplementing the method.

Renderers consume validated projections. They do not search, rescore, fetch
models, or read result directories. [Playback](docs/reference/playback.md) derives
frames from recorded observations without changing the search history.

`scripts/check_architecture.py` checks these import boundaries, including relative
imports, and rejects undeclared modules. Place a new responsibility in the module
map and its matching checks.

## Integration boundary

The package accepts explicit inputs and produces versioned results. Data
acquisition, study design, comparisons across runs, and manuscript composition
belong to consuming projects. Exchange released software and result artifacts
rather than importing another checkout.

[Design contracts](DESIGN.md) define invariants, [reliability](RELIABILITY.md)
covers verification and failure handling, and [Contributing](CONTRIBUTING.md)
describes development.
