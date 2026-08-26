---
doc_id: motif-balance-architecture
title: Motif Balance architecture
intent: Define ownership, dependency direction, and module boundaries.
audience:
  - maintainers
  - agent executors
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-26
doc_type: explanation
---

# Motif Balance architecture

Motif Balance is a standalone modular monolith: one repository, one Python
distribution, one public facade, and no runtime dependency on caller
repositories.

## Product boundary

The reusable product spine is:

```text
DesignSpec -> compile -> evaluate -> search -> select -> Portfolio -> artifact bundle
```

Motif Balance owns strict motif and design contracts, deterministic motif
matching and normalization, bounded candidate search, immutable evaluated
candidates, deterministic portfolio selection, and verifiable artifacts. It
does not own source-dataset curation, a biological study, claim acceptance,
figure numbering, manuscript prose, raw optimizer traces, or private storage.

Research Studies owns study configuration, benchmark cohorts, evidence,
interpretation, and claim gates. `manufold` owns accepted digest-pinned figure
snapshots, captions, composition, manuscript builds, and handoffs. Curated
source descriptors remain owned by their data producer.

## Layer direction

```text
errors, constants, and model
  <- formats, compile, and scoring
  <- search and selection
  <- artifacts and report
  <- api
  <- cli
```

- `model.py` contains strict immutable public contracts and no higher-layer
  imports.
- `constants.py` contains only shared literal constants and imports no other
  first-party layer.
- `formats/` parses external representations into strict models; it does not
  choose scientific policy.
- `compile.py` normalizes a specification into evaluator-ready state.
- `scoring.py` is the single matching and public-score authority.
- `search.py` proposes sequences under explicit budgets. It may evaluate a
  proposal but may not reinterpret a score.
- `selection.py` chooses from already evaluated candidates and cannot mutate or
  rescore them.
- `artifacts.py` serializes and verifies canonical bundles. It does not own
  study registration or manuscript import.
- `report.py` renders typed results and cannot recompute scientific state.
- `api.py` is the sole public operation facade.
- `cli.py` adapts files and arguments to the public facade and contains no
  derivations.

`scripts/check_architecture.py` enforces this direction for absolute and
relative imports and fails on unknown first-party modules. Add a new layer only
with an explicit architecture update and tests.

## Deployment boundary

The package produces versioned artifacts. Callers exchange those artifacts,
digests, and explicit external references; they do not import each other's
source trees. Legacy Cruncher Sample is a migration comparison authority until
parity and adoption are proven, not a runtime dependency of this package.
