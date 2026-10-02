# Interpret scores and returned sequences

Verify a result with `motif-balance inspect`. The saved files answer different
questions:

| File | Question |
| --- | --- |
| `design.json` | What DNA length, motifs, roles, and search settings were requested? |
| `motifs.json` | Which probability matrices and backgrounds defined the scores? |
| `candidates.tsv` | Which sequences were selected, and how were they ranked? |
| `matches.tsv` | Which position and strand supplied each motif's strongest match? |
| `manifest.json` | Which method, checkpoints, completion state, and file identities belong to this result? |

## Find the limiting requirement

[Balance](concepts.md#one-objective-for-desired-and-unwanted-matches) is the lowest
requirement satisfaction. Seek satisfaction equals normalized match attainment;
avoid satisfaction is one minus the strongest unwanted attainment.
`matches.tsv` records the direction, attainment, and satisfaction separately. A
low balance can reflect a weak desired match or an unwanted match that remains
strong.

Zero and one are the theoretical raw-score extrema over a single motif-width
word, rescaled to a common range. The reported score scans all placements and
strands. Embedding a maximum-scoring word can attain one, but a complete sequence
need not attain zero as its strongest match. Under nonuniform background, the
most probable nucleotide can differ from the highest log-odds nucleotide.
[Methods](methods.md#scoring-a-candidate) defines this calculation.

## Distinguish recovery from delivery

Best-score checkpoints report computational progress at evaluation counts, not
elapsed time or every improvement. A bounded search reports what it found.
A balance of one reaches the objective's upper bound; a lower recovered score
does not by itself establish an optimum. The best observed
sequence is recorded separately from the selected portfolio because separation
constraints can exclude it.

A portfolio meets the requested count and sequence separation. A retained elite
pool is a bounded set encountered during search. An arrangement collection picks
representatives by site geometry. [Expansion](expand-sequences.md) supplies
sequence alternatives within a selected layout. These outputs have different
selection rules; none estimates the total number of possible solutions.

If constrained selection reaches its work limit, feasibility remains unresolved.
That differs from proving that the supplied pool cannot meet the request. Read
the reported completion and delivery fields before comparing outcomes.

## Biological interpretation

Scores describe agreement with the supplied models, backgrounds, and strand
policy. They are not calibrated binding probabilities or expression predictions.
Shared site coordinates do not establish simultaneous occupancy. Avoidance lowers
the strongest model match as an objective trade-off, rather than guaranteeing
biological specificity. Sequence differences likewise need not imply functional
differences.

Chromatin, cooperativity, construct context, and assay effects require separate
models or experiments. Compare repeated designs under the same model and scoring
rules, and test recovered candidates in the biological context of interest.
