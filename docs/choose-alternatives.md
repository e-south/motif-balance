# Choose different motif arrangements

Select sequences that place the supplied motifs in different relative orders,
strands, or overlaps. Collection selection keeps the strongest representative
of each arrangement from the retained search pool. It does not run another search.

## Continue from a saved design

Use the ArgR/Cra `result` directory produced by the [README example](../README.md#try-a-design).
Both models were searched in 25-base DNA. At the terminal:

```bash
# Keep up to two arrangements and save their sequences, scores, and motif models.
uv run motif-balance collect result --count 2 --out collection.json
# Draw both selected layouts from the saved collection.
uv run motif-balance inspect collection.json --format png --out arrangements.png
```

These representatives have balance **0.855** and **0.801**. If you already saved
`collection.json` while following the README, use it or choose a new output name.
Add `--candidate 2` to inspect one member. The collection includes the models
needed to recheck each displayed sequence. PNG export uses the visualization extra.

For the same selection in Python:

```python
from motif_balance.artifacts import read_verified_portfolio
from motif_balance.alternatives import rank_architectures

# Load the saved models and rescore the retained search records.
saved = read_verified_portfolio("result")
# Include the retained pool, not just the four candidates returned by design.
pool = tuple(item.sequence for item in saved.manifest.elites)
ranking = rank_architectures(pool, saved.spec, grouping="interval_topology")

# Request two arrangements and report what the retained pool can deliver.
collection = ranking.select_up_to(2)
print(f"Returned {collection.delivered_count} of {collection.requested_count} arrangements")
for rank, member in enumerate(collection.members, 1):
    print(f"Arrangement {rank}: balance {member.evaluation.balance_score:.3f}")
```

The saved search retained 256 sequences. Ranking groups their selected motif
sites and orders the representatives by balance. A shortfall describes that pool,
not every arrangement possible at this DNA length.

## Choose what counts as a different arrangement

| Choice | Meaning |
| --- | --- |
| `grouping="interval_topology"` | Distinguish motif identity, relative strands, and the ordering or equality of site boundaries |
| `grouping="exact_offsets"` | Also distinguish exact spacing between matches; the Python default |
| `select(K)` | Require exactly K available arrangements |
| `select_up_to(K)` | Return up to K arrangements and report any shortfall |

Each motif contributes its selected strongest match. Moving the complete layout
along the DNA does not create another arrangement. With both-strand scanning,
reversing the complete duplex is also equivalent. The
[grouping reference](reference/architecture-ranking.md#what-counts-as-an-architecture)
explains ties, boundary relationships, and returned fields.

<details>
<summary>Inspect the second arrangement</summary>

Append this to the Python example to draw the second representative.

```python
from motif_balance import Candidate
from motif_balance.inspection import inspect_candidate
from motif_balance.inspection.render import render_candidate_svg
from motif_balance.model import candidate_id_for_sequence

# Attach the collection rank to the selected, already-scored sequence.
representative = ranking.representatives[1]
candidate = Candidate(
    candidate_id=candidate_id_for_sequence(representative.evaluation.sequence),
    rank=representative.rank,
    **representative.evaluation.model_dump(mode="python"),
)
# Rescore its sites, then generate SVG bytes and the corresponding score record.
candidate_review = inspect_candidate(candidate, saved.spec)
svg = render_candidate_svg(candidate_review)
review_json = candidate_review.model_dump_json(indent=2)
```

Inspection rescans the sequence; rendering does not. See
[supplied-candidate inspection](reference/result-inspection.md#inspect-a-supplied-candidate)
for export and validation details.

</details>

## Expand the selected layouts

To vary nucleotides while retaining each layout, continue from the collection
saved by the terminal command:

```bash
# Return sequence alternatives for each layout, all with balance at least 0.8.
uv run motif-balance expand collection.json --all --min-balance 0.8 --out expanded
```

The result has a FASTA and per-motif score table for each arrangement. Every
parent must meet the floor. Expansion cannot supply a missing arrangement.
[Sequence expansion](expand-sequences.md) explains the checks and limits;
[degenerate libraries](diversify-sequences.md) provide a separate ambiguity-template output.

Arrangement grouping does not enforce nucleotide separation. For a fixed-size
set with an explicit distance requirement, use [portfolio selection](reference/portfolio-selection.md)
on the full retained pool. Both operations require a design without positive
`min_distance`. Verified loading checks file digests and stored scores. If you
kept the producer's bundle identity, pass `expected_bundle_id` to verify that
identity as well.
