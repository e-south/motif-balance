---
doc_id: motif-balance-architecture
title: Motif Balance architecture
intent: Define ownership, dependency direction, and module boundaries.
audience:
  - maintainers
  - agent executors
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-27
doc_type: explanation
journey:
  - maintain
---

# Motif Balance architecture

Motif Balance is a standalone modular monolith: one repository, one Python
distribution, one public facade, and no runtime dependency on caller
repositories. The canonical ontology, semantic versions, and cross-owner
artifact boundaries are defined in [the information architecture](IA.md).

## Product boundary

The reusable product spine is:

```text
DesignSpec -> compile -> evaluate -> search -> select -> Portfolio -> artifact bundle
```

Motif Balance owns strict motif and design contracts, deterministic motif
matching and normalization, bounded candidate search, immutable evaluated
candidates, deterministic portfolio selection, and verifiable artifacts. It
does not own source-data curation, comparison design, claim acceptance,
presentation, raw optimizer traces, or artifact retention. Callers own those
concerns and cross this boundary only through explicit inputs or immutable
verified artifacts.

## Layer direction

```text
errors, constants, and model
  <- formats, compile, and scoring
  <- search and selection
  <- artifacts and receipt
  <- inspection/{verify, project, render}
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
  downstream registration or presentation.
- `receipt.py` defines the runtime receipt and execution-workspace identity
  without changing canonical bundle identity.
- `inspection/verify.py` carries the path-bound, already verified source into
  review without exposing it to renderers.
- `inspection/project.py` replays authoritative scores and produces the one
  immutable, path-free `ResultInspection`.
- `inspection/render/` turns only that projection into text, JSON, SVG, or one
  self-contained HTML composition. It cannot read artifacts, search, rescore,
  discover stores, compare cohorts, or accept evidence.
- `inspection/catalog.py` is a hidden integration utility over explicit result
  references; it is not the product navigation model.
- `api.py` is the sole public operation facade.
- `cli.py` adapts files and arguments to the public facade and contains no
  derivations.

`scripts/check_architecture.py` enforces this direction for absolute and
relative imports and fails on unknown first-party modules. Add a new layer only
with an explicit architecture update and tests.

## Deployment boundary

The package produces versioned artifacts. Callers exchange those artifacts,
digests, and explicit external references; they do not import each other's
source trees. Placement and retention are caller concerns and do not change
product identities or semantics.
