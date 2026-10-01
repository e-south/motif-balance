# Motif Balance documentation

Start with the [ArgR/Cra walkthrough](../README.md#try-a-design) to design DNA,
select arrangements, and expand their sequences. Use the guides below to change
inputs, choose outputs, or interpret scores.

## Design and inspect DNA

| Task | Guide |
| --- | --- |
| Start a uv project | [Installation](installation.md) |
| Run, inspect and export a first design | [Quickstart](quickstart.md) |
| Work with transcription-factor profiles | [Twelve-model recorded search](../examples/twelve-motifs/README.md) |
| Prepare count or probability matrices | [Motif inputs](motif-models.md) |
| Write a design request | [Design specification](design-spec.md) |
| Design from Python | [Python tutorial](python-api.md) |
| Evaluate DNA you already have | [Sequence scoring](score-sequences.md) |
| Select different motif arrangements | [Choose alternatives](choose-alternatives.md) |
| Obtain qualifying sequence lists within selected layouts | [Expand sequences](expand-sequences.md) |
| Construct a completely checked ambiguity template | [Degenerate libraries](diversify-sequences.md) |
| Understand scores and saved results | [Interpretation](interpreting-results.md) and [visual inspection](reference/result-inspection.md) |

## Scoring, search, and saved results

- [Define balance](concepts.md) and [follow the scoring and search calculations](methods.md).
- [Compare motif preferences before searching](pair-assessment.md).
- [Look up Python operations and CLI arguments](reference/public-contract.md).
- [Record search states](reference/search-observations.md) and [animate them](reference/playback.md).
- [Select a fixed-size set with sequence-separation requirements](reference/portfolio-selection.md).
- [Record the software and runtime used for a search](reference/execution-receipts.md).

## Maintain the package

Start with [Contributing](../CONTRIBUTING.md). The
[architecture overview](../ARCHITECTURE.md) and [module map](reference/module-map.md)
locate the implementation of each operation.
[Design contracts](../DESIGN.md), [reliability](../RELIABILITY.md) and
[security](../SECURITY.md) define the guarantees to preserve.
Use the [release procedure](reference/prerelease.md) to prepare distributions.
