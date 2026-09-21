---
doc_id: motif-balance-portfolio-selection
title: Select a differentiated portfolio
intent: Select and replay a full supplied-pool portfolio under explicit separation and architecture requirements.
audience: [API consumers]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-21
doc_type: reference
journey: [integrate]

---

# Select a differentiated portfolio

Use `motif_balance.alternatives.select_portfolio(sequences, spec, policy)` when
you need a fixed number of candidates meeting explicit separation requirements.
It rescans your supplied sequences, then favors the set with the strongest
weakest member. It does not search for new DNA or silently return fewer candidates.

Use the current source installation or a build containing this API. It is a separate
operation from generation and from [diagnostic architecture ranking](../choose-alternatives.md):
do not first discard all but one sequence per architecture. Another member of
the same class may combine better with other candidates.

## Runnable example

These synthetic models prefer AA and CC. Two supplied sequences satisfy both
models while reversing their order. Run from any directory; no files or external
models are needed.

```python
# Import the models and operations used in this example.
from motif_balance import DesignSpec, MotifModel, MotifSpecification
from motif_balance.alternatives import select_portfolio, verify_portfolio_selection
from motif_balance.model.selection import PortfolioPolicy, PortfolioSelection

# Create two motifs that prefer AA and CC.
models = tuple(
    MotifModel(
        motif_id=name,
        probabilities=(tuple(0.7 if base == preferred else 0.1 for base in "ACGT"),) * 2,
        background=(0.25,) * 4,
    )
    for name, preferred in (("first", "A"), ("second", "C"))
)
# Declare the scoring context for the supplied four-base sequences.
spec = DesignSpec(
    schema_version="design-spec/v3",
    specifications=tuple(MotifSpecification(motif=m, direction="seek") for m in models),
    length=4,
    count=1,
    strands="forward",
    evaluations=1,
    seed=7,
)
# Request two different arrangements with a minimum footprint distance.
policy = PortfolioPolicy(
    count=2,
    separation="selected_footprint",
    min_distance=0.2,
    equivalence="forward",
    architectures="distinct",
)
# Supply the sequences from which the collection may be selected.
pool = ("AACC", "CCAA", "ACAC", "CACA", "AAAA", "CCCC")
# Choose the strongest feasible two-sequence set.
result = select_portfolio(pool, spec, policy)
# Check that the selected set has a proven optimal quality within this pool.
assert result.status == "optimal" and result.quality is not None
# Check that the selected members have a defined separation.
assert result.minimum_separation is not None
# Print the delivered count and weakest balance.
print(f"{result.status}: {result.delivered_count} candidates, weakest balance {result.quality:.3f}")
# Print the selected DNA sequences.
print(", ".join(member.evaluation.sequence for member in result.members))
# Print the smallest separation between selected members.
print(f"Minimum footprint separation: {result.minimum_separation:.3f}")
# Serialize and reload the selection record.
record = PortfolioSelection.model_validate_json(result.model_dump_json())
# Replay the record against the original pool and check that it agrees.
assert verify_portfolio_selection(record, pool) == result
```

The output is AACC and CCAA, both with balance one and footprint separation
one. The original request's `count=1` is retained as generation context;
`policy.count=2` is the explicit selection request. No generation ran here.
The example's threshold is a user choice, not a biological cutoff.

## Inputs and identity

Supply a bounded tuple or list of uppercase, equal-length A/C/G/T strings and
the current directional `DesignSpec` defining their models, directions, length,
and strands. At least two specifications are required. Keep the generation
request unchanged. A positive generation `min_distance` is refused, because
this operation must not silently reinterpret it as the new separation rule.

For forward scanning, declare `equivalence="forward"`; for both-strand scanning,
declare `"reverse_complement"`. The latter collapses literal reverse complements
before scoring, using the lexically smaller sequence. The selected canonical
sequence may therefore be the reverse complement of an input. Nothing changes
after evaluation. This also makes selected-site ties independent of the supplied
orientation. Permuting the pool leaves the result unchanged; duplicate literals
change its input multiset receipt, not its scored candidates.

`PortfolioPolicy` requires count, separation, minimum distance, equivalence,
and `architectures="distinct"` or `"unrestricted"`. Its only selector is
`bounded_bottleneck_v1`. Policy identity includes the work limits. Unknown fields,
unknown versions, implicit conversions, and automatic policy fallback are refused.

## Separation and selected architectures

`selected_footprint` compares bases within the union of both candidates' selected
motif footprints. Test each permitted relative orientation and take the smaller
mismatch fraction. Coordinates and footprints are transformed together; they
are not rescanned during distance measurement. Forward wins an exact distance
tie. The returned pair record identifies that orientation.
Threshold comparison allows an absolute numerical tolerance of `1e-12`;
quality ordering itself uses the recorded floating-point scores.

Changes outside both footprints cannot alone satisfy a positive footprint
threshold. This rule is deliberately different from architecture ranking's
whole-sequence-first orientation choice. It is a separation function, not a
proven metric or a measure of functional diversity. `hamming` instead compares
the full fixed-length sequences under the same declared orientation policy.

Distinct architectures use relative selected-site positions and strands after
removing common translation and permitted global reversal. A different
architecture need not have a large spacing difference. Its sites are the
deterministically selected strongest matches, not every tied or possible match.
For avoid specifications these are the strongest unwanted sites.

For two models of widths `w1,w2`, the necessary architecture bound is
`2*L-w1-w2+1` for forward scanning and twice that for both strands. At equal
width and full compression it is two for both strands: demanding four distinct
architectures cannot work. This upper bound is not the attainable count;
palindromes, tied sites, and motif preferences may reduce support further.

## Quality, completion, and proof

Among feasible full sets, prefer the highest minimum balance, then highest
total balance, then the lexically smallest sorted sequence tuple. Returned
members are ordered by descending balance and lexical sequence. The exact
finite-pool search uses bounds and a capped traversal; it can return a valid
full witness even when the best achievable finite-pool quality is unresolved.

| `status` | Meaning |
| --- | --- |
| `optimal` | A full set was found and the stated ordering is optimal within this supplied canonical pool. |
| `feasible` | A full set satisfies every requirement; the work limit prevents an optimality certificate. |
| `unresolved` | No full witness was found before the work limit. |
| `pool_infeasible` | Completed finite-pool traversal proves no full set meets the requirements. |
| `architecture_bound` | The necessary pair-placement bound rules out the requested distinct count before candidate scoring. |

Only the first two outcomes deliver members and define `quality`: their weakest
balance. Every undelivered outcome has no members and `quality=None`, not zero
or the quality of a partial set. For one member the separation is undefined.
Pool infeasibility never becomes a whole-sequence-space assertion. Feasible
sets can be useful without claiming they are optimal.

## Work and verification

Input admission reuses the supplied-pool limits: 50,000 records, ten million
bases, and 100 million scoring-base operations. Before candidate scoring or
quadratic preparation, selection also admits a conservative distance-work
bound, including the selected-pair receipt measurement pass. The default is ten
million terms; the explicit maximum is 500 million. Independent caps allow at
most 500,000 pair measurements and 250,000 prepared motif-pair entries. No
distance work is prepared for a singleton request or an undersized pool.

`work_limit` defaults to one million and accepts positive integers up to that
cap. One unit is a popped traversal state, including pruned and terminal states.
Compatibility uses bounded bitsets rather than a dense float distance matrix.
The search stops exactly at its limit; it does not retry with a larger allowance.
Work bounds are not CPU-instruction counts or runtime guarantees.

The immutable result binds the original request and problem, policy, sorted
input-multiset digest, raw/literal/canonical counts, scoring calls, conservative
distance terms, traversal work, members, selected architectures, all achieved
pair separations, quality, and proof status. `result_digest` and `policy_digest`
identify their canonical contents. `search_evaluations` is always zero.

Parsing JSON checks structure and cross-field invariants, not scientific truth.
Retain the explicit pool and trusted request, then call
`verify_portfolio_selection(result, pool)` to rescore and rerun selection,
including its proof status. Replay is additional work. Neither a digest nor
replay proves that a supplied search archive retained every useful sequence.
This record is not a search bundle or a scientific acceptance receipt.

Use [supplied-candidate inspection](result-inspection.md#inspect-a-supplied-candidate)
for the existing duplex/logo view of any selected evaluation. Selection does not
need a second renderer, repository-specific model loader, or new file format
adapter.
