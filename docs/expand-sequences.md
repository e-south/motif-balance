# Expand a collection into sequence lists

Expansion supplies nucleotide alternatives for each selected motif-site layout.
Every returned sequence retains the sites and meets your minimum balance.
Scores above the floor can still differ.

```bash
# Keep each arrangement separate and require every sequence to meet the same floor.
uv run motif-balance expand collection.json --all --min-balance 0.8 --out expanded
```

The directory contains a FASTA and per-motif score table for each arrangement,
plus `collection.json` with the complete record. Omit `--all` to expand the first
representative, or select `--candidate 2`. A single-parent directory contains
`sequences.fasta`, `scores.tsv`, and `expansion.json`. A missing arrangement stays
missing. If any supplied parent is below the floor, the collection is refused
before expansion starts.

## Choose quality and practical limits

`--min-balance 0.8` requires every desired normalized score to be at least 0.8.
For an unwanted model, its avoidance component, one minus its score, must meet
the floor. Every desired model's selected best-match coordinates and strand stay
fixed under the existing tie rule. Uncovered DNA stays unchanged. These scores
measure model agreement, not preserved binding or expression.

By default, expansion returns up to 256 sequences per arrangement and evaluates
up to 4,096 sequences, including the parent. Set `--max-variants` and
`--max-evaluations` to change those allowances. Every qualifying sequence tested
before stopping is retained. The operation stops before evaluating another
sequence when either limit has been reached.

The summary states the number retained, the number tested, and why expansion
stopped. Reaching an allowance does not establish expansion capacity. A
`frontier exhausted` result means there are no untested one-base neighbours of
the qualifying sequences reached from this parent. It does not exclude
qualifying sequences separated by failing intermediates.

## What the operation tests

Start from the selected DNA, test single-base alternatives, and retain those
that pass the score and site checks. Then test one-base alternatives from each
retained sequence in discovery order. Positions run left to right and alternative bases
follow A/C/G/T order. Each distinct sequence is evaluated once. All comparisons
use the original parent’s sites; site movement cannot accumulate over steps.

This bounded traversal does not enumerate the full sequence space or optimize
Hamming distance. Its explicit lists need not form a complete ambiguity product.
For example, AA, AC, and CA may qualify while CC fails. Returning those three
sequences is valid; writing MM would wrongly include CC.

For a template whose every combination has been checked, use the separate
[degenerate-library operation](diversify-sequences.md). That extra requirement
can exclude individually qualifying sequences.

## Python and verification

```python
from motif_balance.variants import expand_collection, load_expansion

# Reuse the models and selected layouts already carried by the collection.
expanded = expand_collection(report, min_balance=0.8, max_variants=256)

# Each arrangement has its own sequence list, scores, and compact test history.
first = expanded.libraries[0]
print(len(first.variants), first.evaluations_used, first.stop_reason)

# Replay one saved expansion without rerunning the original design search.
verified = load_expansion(first.model_dump_json())
```

For external DNA, import `expand` from `motif_balance.variants` and call
`expand(sequence, spec, min_balance=0.8)`. An optional
boolean `editable_mask` has one entry per forward-reference position and replaces
the default set of editable positions, so it can explicitly permit flanking
bases. The CLI equivalent is `--editable-mask`, using `0` and `1`. The complementary
strand is determined by the sequence, not edited independently.

## Resource and record contracts

Full motif-match records are retained only for returned sequences. Each rejected
test stores a source-sequence index, edited position and base, balance, and
rejection reason. An exact two-bit sequence identity avoids duplicate scoring
without retaining a second copy of every rejected DNA string. No combinatorial
space is materialized.

Each expansion admits at most 1,024 returned sequences, 100,000 evaluations,
one billion positional scoring operations, 32 million conservative cached-base
units, 50,000 returned match records, and a conservative 64 MB JSON output bound.
The byte bound includes the DNA strings within match records, not just their count.
Collections contain at most 16 supplied
arrangements. Aggregate output and work are checked before any member is
expanded, including the complete collection's 64 MB output bound; members run
sequentially. `--max-total-score-operations` can raise
the collection's total sequential-work allowance up to 16 billion while keeping
per-member and aggregate output bounds.

`sequence-expansion/v1` and `expanded-collection/v1` are explicit-list records.
They do not silently reinterpret historical `variant-library` product records.
`load_expansion` rejects duplicate JSON keys and inputs over 64 MB, then replays
all decisions, scores, sites, and limits. Structural parsing alone is not score
verification. Producer version and build-lock fields are provenance declarations.
