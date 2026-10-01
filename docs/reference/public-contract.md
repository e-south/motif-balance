# API, commands, and saved formats

Start with the [Python tutorial](../python-api.md) for runnable examples or the
[README](../../README.md#try-a-design) for the command-line workflow.

## Python

The top-level interface exports `MotifModel`, `MotifSpecification`, `DesignSpec`,
`MotifMatch`, `Candidate`, `Portfolio`, `design`, and `score`.

- `score(sequence, spec)` returns an immutable evaluation. Requested output count
  and portfolio separation do not affect its score. Model, length, strand, and
  scoring validation still apply.
- `design(spec)` returns exactly `spec.count` ranked candidates or raises a typed
  error. `Portfolio.write(path)` publishes a new, verified result bundle.
- `design(spec, method=...)` accepts `annealed` (default), `greedy`, `random`, or
  `exhaustive`. Exact enumeration requires a budget covering the complete space.
  `initialization="independent"` selects eight independent starts instead of the
  default related starts for guided search. The method and initialization belong
  to run identity. See [methods](../methods.md#explicit-comparison-methods).

Advanced operations are explicit submodule imports:

| Operation | Result and reference |
| --- | --- |
| `variants.expand`, `variants.expand_collection` | Qualifying sequence lists under declared work and output limits. [Expansion](../expand-sequences.md) |
| `variants.diversify`, `variants.diversify_collection` | Complete, jointly checked ambiguity products. Absolute floor and parent-relative loss are mutually exclusive. [Degenerate libraries](../diversify-sequences.md) |
| `alternatives.rank_architectures` | Scores a supplied pool and ranks one representative per arrangement class. `select` requires an exact count; `select_up_to` reports partial delivery. [Collections](../choose-alternatives.md) |
| `alternatives.measure_prefixes` | Measures an explicit representative order without changing scores. [Ranking reference](architecture-ranking.md) |
| `alternatives.select_portfolio`, `verify_portfolio_selection` | Count, separation, and optional arrangement constraints over a supplied pool. [Constrained selection](portfolio-selection.md) |
| `assessment.assess_pair`, `assess_motifs` | Shared-base preference loss for two, or up to four, desired models without sequence search. [Assessment](../pair-assessment.md) |
| `inspection.inspect_result` | Verifies a bundle or explicit execution workspace. [Inspection](result-inspection.md) |
| `inspection.inspect_candidate` | Rescores a supplied candidate under explicit models, without asserting its origin or rank. [Candidate inspection](result-inspection.md#inspect-a-supplied-candidate) |
| `api.design_observed`, `playback.inspect_playback` | Records and replays bounded search observations. [Observations](search-observations.md) and [playback](playback.md) |

Arrangement grouping is `exact_offsets` by default in Python or
`interval_topology` for boundary order, equality, and strands. The `collect` CLI
uses interval topology. Arrangement ranking does not enforce sequence separation;
use constrained selection when that is required.

## Command line

```text
design    search for DNA from a saved request
inspect   review sequences, sites, and scores in a saved design
collect   choose different motif arrangements from retained sequences
expand    retain qualifying nucleotide sequences at selected sites
diversify construct a completely checked degenerate template
score     score DNA you already have
assess    compare motif preferences before sequence search
motif     prepare a motif model from an explicit source
animate   replay recorded search states
```

Each command's `--help` lists its controls. Output paths must be new. `inspect`
verifies bytes, schemas, identities, and scores before drawing views. `collect`
exports a self-contained report; its optional `--expected-bundle-id` checks an
externally retained identity. Without the original bundle, a report's source
identity remains a declaration.

Motif conversion reads an explicitly supplied source; it does not fetch
databases. Advanced `orchestration execute` binds a run to an exact wheel and
producer revision. See [conversion](motif-conversion.md) and
[execution records](execution-receipts.md).

## Artifacts

A result bundle contains `design.json`, `motifs.json`, `candidates.tsv`,
`matches.tsv`, `manifest.json`, and derived `candidates.fasta`. Its manifest binds
every member by path, size, and SHA-256, including the best observed evaluation
when distance constraints exclude it from the selected portfolio. Verification
replays stored scores and sites without rerunning search. Text and graphical
reviews remain regenerable outputs outside that bundle.

| Record | Current format |
| --- | --- |
| Design, motif, and result bundle | `design-spec/v3`, `motif-model/v2`, `run-manifest/v7` |
| Scoring and search diagnostics | `relative_pwm_attainment_v2`, `search-diagnostics/v4` |
| Arrangement ranking and collection | `architecture-ranking/v4`, `architecture-collection/v1`, `collection-report/v1` |
| Explicit expansion | `sequence-expansion/v1`, `expanded-collection/v1` |
| Degenerate products | `variant-library/v3`, `collection-variants/v1` |
| Constrained selection | `portfolio-policy/v1`, `portfolio-selection/v2` |
| Inspection | `motif-balance.result-inspection/v5`, `motif-balance.candidate-inspection/v2` |
| Playback | `playback-inspection/v2` |
| Attested execution | `motif-balance.execution-workspace/v1` |

Bounded search engines use version 2; explicit exhaustive enumeration uses
version 1. Earlier bounded runs and unsupported formats require their producing
software. The degenerate-library reader additionally supports explicit v2 replay;
its unchanged quality rule but different evaluation accounting is described in
[the library guide](../diversify-sequences.md). Versions are not inferred or
silently converted.

[Result integrity](../../RELIABILITY.md) defines deterministic encoding,
publication, and verification. Model scores and verified files establish a
computational result; biological interpretation requires experimental evidence.
