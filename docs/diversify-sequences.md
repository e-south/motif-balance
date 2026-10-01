# Construct checked degenerate libraries

Use `diversify` to build an IUPAC template whose every encoded sequence meets
your score requirement and retains the selected motif sites. Requiring all
combinations to pass can exclude individually qualifying sequences. For an
explicit sequence list, use [expansion](expand-sequences.md).

```bash
# Expand every arrangement in the saved collection above one absolute quality floor.
uv run motif-balance diversify collection.json --all --min-balance 0.8 --out variants
```

The output directory contains `collection.json` with the original selection and libraries,
plus a FASTA, score table, and substitution map for each arrangement. Templates
remain separate because merging their allowed bases could encode unchecked DNA.
A missing arrangement remains missing. If a parent fails the requested quality
rule, the operation reports its rank and stops before constructing any library.

To expand just one representative, omit `--all` or choose `--candidate 2`.
The single-library directory contains `library.json`, `variants.fasta`,
`scores.tsv`, and `substitutions.svg`. You can also select a candidate from a
saved design directory or supply external concrete DNA with its design request.

```python
from motif_balance.variants import diversify, diversify_collection

# Keep every sequence above the chosen balance floor, with the selected sites fixed.
library = diversify(candidate.sequence, spec, min_balance=0.8)
print(library.template, library.encoded_sequence_count)

# Apply the same rule to every delivered member of a parsed CollectionReport.
expanded = diversify_collection(report, min_balance=0.8)
print(len(expanded.unique_sequences))
```

The operation rescores parents using the prepared models, strand policy, and tie
rule. It requires at least one desired model and does not run the optimizer.

## What is preserved

Every desired model's selected highest-scoring window keeps its parent's start,
end, and strand. Even an equally scoring alternative site is rejected if the
existing tie rule selects different coordinates or a strand.

Choose one quality rule. `min_balance=0.8` requires every variant's objective
components to be at least 0.8. For desired models these are normalized scores;
for unwanted models they are one minus the normalized score. The parent must
already qualify. This mode places no additional limit on parental score loss.

Alternatively, `max_score_loss=0.02` limits each desired score's decline and each
unwanted score's increase to two hundredths relative to the parent. It is the
default when neither rule is supplied. Explicitly supplying both rules is an
error. Neither threshold is a binding cutoff. Comparisons allow `1e-12` roundoff.

By default, only positions covered by the selected desired sites can change.
An optional `editable_mask` is a tuple of booleans, one per forward-reference
position. An explicit mask can permit flanking positions. The complementary
strand follows from the sequence and is never diversified independently.

## What the library contains

`max_variants` is an integer from 1 to 1,024, including the parent; the default is 256. It is a ceiling.
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
greedy construction does not guarantee the largest possible library. Advanced
Python callers can compare `construction_order="least_loss"` (the default),
`"greatest_loss"` (reverse that complete order), and `"hashed"` (stable input-based
order). The selected order is saved and replayed; changing it can change the library.

`stop_reason` distinguishes a size-limited construction from exhaustion of the
passing expansions in this order. Counts record expansions rejected by size and
score/site checks. A size-limited result need not contain exactly the cap because
product sizes can jump past it.

## Export and inspect

```bash
# Supply your own sequence with the request that defines its models and length.
uv run motif-balance diversify design.yaml ACGT --max-score-loss 0.02 --out variants

# Or request only FASTA from the first candidate in a saved design.
uv run motif-balance diversify result --candidate 1 --out variants.fasta
```

Replace `ACGT` with your DNA of the request's exact length. A filename ending in
`.json`, `.fasta` or `.fa`, `.tsv`, `.svg`, or `.txt` selects that export. An output
path without a suffix creates a directory with all four exports, calculating the
library once. Use `--format all` for a directory whose name contains a dot.
CLI `--editable-mask` accepts one `0` or `1` per position. Existing files and
directories are never overwritten, and exports must remain outside a saved design.
Unsupported export options and nonbinary masks are rejected before loading or
rescoring saved candidates. Mask length is checked against the selected DNA.
The JSON is the complete handoff; FASTA and TSV are derived views. The SVG aligns
the parent duplex, selected intervals, and four nucleotide rows. Cells distinguish
jointly retained options from substitutions that pass alone. Hover text supplies
each model's component change and selected site. Scores concern this DNA context;
adding flanks requires rescoring the resulting larger sequence.

Each library is limited to one billion estimated positional scoring operations,
32 million cached sequence bases, and 50,000 diagnostic/output match records.
A collection contains at most 16 members and 50,000 combined output match records.
Its members are expanded sequentially, so their scoring caches do not accumulate.
The default total work allowance is also one billion operations. If preflight
reports that a collection needs more total work, explicitly admit that amount:

```bash
# Allow more sequential work while keeping each library's memory and size limits.
uv run motif-balance diversify collection.json --all --min-balance 0.8 \
  --max-variants 1024 --max-total-score-operations 2000000000 --out variants
```

The corresponding Python option is `max_total_score_operations`. It accepts
positive integers up to 16 billion and does not change which variants qualify.
Preflight checks every parent before constructing any library or writing output.
Conservative work estimates use all editable single options and the library cap;
they are not elapsed time or the number of evaluations actually performed.
These evaluations are separate from the original search allowance.

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
For an already parsed record, use `verify_library`. It checks the complete record
before replay, including nested summaries and integer effort counts. A copied
Python object is not assumed to remain valid. Producer-version and build-lock
fields remain recorded declarations, not cryptographically authenticated history.

The current format is `variant-library/v3`, with exactly one quality rule and an
explicit construction order. Version 1 libraries require their producing
software; this reader rejects them rather than inferring their settings.
`collection-variants/v1` binds one separate versioned library to every delivered member.
Its model validates structure; replay each library with `verify_library` to check
scores and construction decisions. Collection verification scans are separate
from each library's reported construction count.

### Checking a proposed expansion

The constructor first checks the worst allowed score at each selected desired
site by adding the lowest permitted contribution at each position. An expansion
that fails this necessary quality check is rejected without enumerating it. All
accepted members still receive a complete rescan to check the selected sites and
any unwanted models. The nucleotide-addition order is unchanged.

The handoff separates size-limit, quality, and selected-site rejections. These
counts identify the first failing check for each proposed addition, not all
possible reasons a product could fail. Quality refers to the declared balance
floor or parental-loss rule. It also reports how many quality failures were
detected by the preliminary check. These are diagnostic records, not statements
that no larger valid library exists.

Version 3 records these checks and actual rescan counts. Version 2 libraries
remain readable and replay with their recorded construction and accounting.
