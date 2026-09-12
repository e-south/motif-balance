---
doc_id: motif-balance-interpreting-results
title: Interpreting Motif Balance results
intent: Explain result fields, diagnostics, and the boundary of product claims.
audience:
  - users
  - bundle consumers
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-08
doc_type: explanation
---

# Interpreting Motif Balance results

Verify a bundle before reading it. Then use each file for one question:

- `design.json`: what was requested?
- `motifs.json`: what model content defined the score?
- `candidates.tsv`: which immutable sequences were selected and ranked?
- `matches.tsv`: which span and strand won for each candidate–motif pair?
- `manifest.json`: which semantics, search provenance, diagnostics, and bytes
  form this result?

## Find the limiting requirement

For a directional design, `balance_score` is the lowest **specification
satisfaction**. A seek requirement's satisfaction equals its relative PWM
attainment; an avoid requirement's satisfaction is one minus its strongest
attainment. `matches.tsv` retains both the direction and satisfaction alongside
the normalized match score. Inspect the limiting requirement rather than
reading the aggregate as a probability. A weak balance can reflect either a
poor desired match or an unwanted match that remains too strong.

## Read attainment on its declared scale

Zero is the theoretical minimum raw LLR over one motif-width word, and one is
the corresponding maximum. Both word-level extrema are attained by choosing a
minimum- or maximum-scoring base at every motif position. Motif Balance reports
the best score across all valid placements and orientations: embedding a
score-maximizing word can attain one, while no sequence need have zero as its
reported best match. The conventional probability consensus can differ from
the score-maximizing reference under a nonuniform background. Two scores are
directly comparable only when motif content, score version, strand rule, and
attainment authority are identical.

The reported match is the best-scoring sequence realization under the declared
scanner: a matched word at one candidate span and strand. It is not a choice
from a separately supplied motif-variant library. When representative windows
overlap, they share candidate coordinates and bases; that geometry does not
establish simultaneous occupancy, co-binding, or regulatory function.

## Keep hard thresholds separate

Explicit legacy `design-spec/v2` requests with hard ceilings use a different
contract. For these constraint-bearing designs, target and avoider evidence answer different
questions. `balance_score` remains the minimum target-motif score. Every
avoider reports its own best normalized match and declared upper ceiling; the
candidate is feasible only when all avoider scores satisfy those ceilings.
Avoider scores are not subtracted from, averaged with, or otherwise folded
into `balance_score`.

An exact enumeration failure can prove that no sequence satisfies the avoider
ceilings. A budget-limited feasibility failure does not. Portfolio
infeasibility and the independent distance-selection traversal limit are also
reported separately and publish no partial bundle.

## Distinguish search recovery from alternatives

Best-score checkpoints describe computational progress at recorded evaluator
counts, not the exact time of every improvement. A held-step display does not
reconstruct events between checkpoints. Restart-final scores
describe variation among starts. Proposal summaries describe search execution.
They are not posterior samples, biological replicates, or a global-optimality
certificate. Complete enumeration establishes an optimum only when the admitted
sequence space is fully covered. Otherwise the result records the best
evaluation observed under the declared evaluator-call budget separately from
the exact portfolio selected under any distance constraint.

The selected portfolio and retained elite archive are not interchangeable.
The former satisfies the requested count and distance rule; the latter is a
bounded high-scoring collection encountered during search. Neither alone
establishes solution-space size or diversity at matched quality across runs.
Use explicit [search observations](reference/search-observations.md) if those
caller-owned comparisons need bounded samples at declared score thresholds.

The package establishes a self-consistent computational result under declared
inputs. Binding, expression, fitness, cross-context portability, or superiority
to another method requires a separately specified comparison and validation
workflow.
