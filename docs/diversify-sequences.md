---
doc_id: motif-balance-diversification
title: Vary a sequence while retaining its selected sites
intent: Build and export a small score-constrained nucleotide library around one DNA design.
audience: [users, API consumers]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-26
doc_type: how-to
journey: [design, score]
---

# Vary a selected sequence

After choosing a design, you can vary its nucleotides while retaining the selected
motif sites. This complements [arrangement selection](choose-alternatives.md),
which chooses different relative site arrangements from saved candidates.

```python
from motif_balance.variants import diversify

library = diversify(candidate.sequence, spec, max_score_loss=0.02, max_variants=256)
print(library.template, library.encoded_sequence_count)
print(library.minimum_balance, library.maximum_component_loss)
```

The parent can also be an externally supplied A/C/G/T sequence. It is rescored
using the request's prepared models, normalization, strand policy, and tie rule.
The operation requires at least one desired model and does not run the optimizer.

## What is preserved

For every concrete variant, each desired model's selected highest-scoring window
must retain the parent's start, end, and strand. Each desired normalized score may
fall by at most `max_score_loss`. For an unwanted model, its highest score anywhere
on the permitted strands may rise by at most that amount. Thus its avoidance
component, one minus the score, obeys the same loss limit. Comparisons allow
`1e-12` numerical roundoff.

A tolerance of `0.02` means two hundredths on the model-relative score scale.
It is not a percentage change in binding. Even an equally scoring alternative site
is rejected if the existing tie rule selects different coordinates or a strand.

By default, only positions covered by the selected desired sites can change.
An optional `editable_mask` is a tuple of booleans, one per forward-reference
position. An explicit mask can permit flanking positions. The complementary
strand follows from the sequence and is never diversified independently.

## What the library contains

`max_variants` is an integer from 1 to 256, including the parent. It is a ceiling.
The result includes the complete request, parent and variant evaluations, allowed
bases per position, IUPAC template, all single-substitution rescans, verification
summary, and separate diversification evaluation count. A parent-only result means
no additional variants were found under those settings.

The IUPAC template encodes exactly the Cartesian product of the allowed bases.
Every encoded sequence is present in `library.variants` and has passed the checks.
The ordinary `score` operation continues to reject ambiguous DNA.

Single substitutions are ranked by their largest adverse component change, then
position and nucleotide. Starting with the parent, the construction attempts one
additional nucleotide option at a time. An expansion is accepted only if every
new combination passes and the library remains within its cap. An option that
passes alone can therefore be absent from the final template. This deterministic
greedy construction does not guarantee the largest possible library.

`stop_reason` distinguishes a size-limited construction from exhaustion of the
passing expansions in this order. Counts record expansions rejected by size and
score/site checks. A size-limited result need not contain exactly the cap because
product sizes can jump past it.

## Export and inspect

```bash
motif-balance diversify design.yaml ACGT --max-score-loss 0.02 --out library.json
motif-balance diversify design.yaml ACGT --max-score-loss 0.02 --format fasta --out variants.fasta
motif-balance diversify design.yaml ACGT --max-score-loss 0.02 --format tsv --out scores.tsv
motif-balance diversify design.yaml ACGT --max-score-loss 0.02 --format svg --out substitutions.svg
```

Replace `ACGT` with a parent of the request's exact length. CLI `--editable-mask`
accepts one `0` or `1` per position. Existing files are never overwritten.
The JSON is the complete handoff; FASTA and TSV are derived views. The SVG aligns
the parent duplex, selected intervals, and four nucleotide rows. Cells distinguish
jointly retained options from substitutions that pass alone. Hover text supplies
each model's component change and selected site. Scores concern this DNA context;
adding flanks requires rescoring the resulting larger sequence.

The implementation admits at most one billion estimated positional scoring
operations, 32 million cached sequence bases, and 50,000 diagnostic/output match
records. Conservative bounds use all editable single options and the library cap.
A refused request can use a smaller mask or cap. These checks and all diversification
evaluations are separate from the original search allowance. Explicit rescanning
is authoritative; no information-content heuristic substitutes for it.


## Verify a saved library

```python
from pathlib import Path
from motif_balance.variants import load_library

# Reconstruct the library from its parent and settings, then compare every record.
library = load_library(Path("library.json").read_bytes())
```

Use `load_library` for a JSON handoff. It rejects duplicate keys and inputs above
64 MB, then reruns the bounded diversification operation. Scores, selected sites,
allowed bases, substitution decisions, evaluation counts, rejection counts, and
stopping reason must agree. Numerical comparisons allow only `1e-12` absolute
roundoff. This verifies the library without repeating the original design search.

Direct `VariantLibrary.model_validate_json` checks the data structure and internal
relationships only; it does not verify the recorded scores against the models.
For an already parsed record, use `verify_library`. Producer-version and build-lock
fields remain recorded declarations, not cryptographically authenticated history.
