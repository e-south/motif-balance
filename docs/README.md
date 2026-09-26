---
doc_id: motif-balance-docs-index
title: Motif Balance documentation
intent: Find instructions for sequence design and package maintenance.
audience: [users]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-20
doc_type: index
---

# Motif Balance documentation

Supply motif models and an available DNA length, search for candidates, then
inspect the strongest match to each model. Start with installation and a first
design; use the references when you need to change an input or interpret a result.

## Design and inspect DNA

| Task | Guide |
| --- | --- |
| Install a wheel or source checkout | [Installation](installation.md) |
| Run, inspect and export a first design | [Quickstart](quickstart.md) |
| Work with transcription-factor profiles | [Twelve-model recorded search](biological-example.md) |
| Prepare count or probability matrices | [Motif inputs](motif-models.md) |
| Write a design request | [Design specification](design-spec.md) |
| Design from Python | [Python tutorial](python-api.md) |
| Evaluate DNA you already have | [Sequence scoring](score-sequences.md) |
| Vary a sequence within its selected arrangement | [Diversify a sequence](diversify-sequences.md) |
| Select different motif arrangements | [Choose alternatives](choose-alternatives.md) |
| Understand scores and saved results | [Interpretation](interpreting-results.md) and [visual inspection](reference/result-inspection.md) |

## Understand and extend the method

[Concepts](concepts.md) explains the balanced objective.
[Methods](methods.md) defines scoring and search.
[Pair assessment](pair-assessment.md) examines shared-base preferences before
sequence search. [Limitations](limitations.md) describes what these model scores
can establish.

For integration, use the [API and CLI reference](reference/public-contract.md),
[search observations](reference/search-observations.md),
[search playback](reference/playback.md),
[constrained portfolio selection](reference/portfolio-selection.md), and
[execution records](reference/execution-receipts.md). The optional
[claim-language checker](reference/claim-language.md) provides limited wording
checks for exported results.

## Maintain the package

Start with [Contributing](../CONTRIBUTING.md). The
[architecture overview](../ARCHITECTURE.md) and [module map](reference/module-map.md)
locate code; [information architecture](../IA.md) locates records and their meaning.
[Design contracts](../DESIGN.md), [reliability](../RELIABILITY.md) and
[security](../SECURITY.md) define the guarantees to preserve.
Use the [release procedure](reference/prerelease.md) to prepare distributions.
