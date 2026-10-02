# Check and adapt a design

Start with the [README installation and input preparation](../README.md#1-install-and-prepare-the-profiles)
to obtain the ArgR/Cra profiles and `design.yaml`. Use that request to check
inputs, export figures, and compare search methods. For Python, use the
[Python tutorial](python-api.md).

## 1. Check the inputs and run the search

The ArgR/Cra request asks for four 25-base sequences. Its
[source profiles and preparation](../examples/argr-cra/README.md) accompany the inputs.

```bash
# Check the motif files, DNA length and search settings without running a search.
uv run motif-balance design design.yaml --check

# Evaluate up to 4,096 candidates and save four sequences.
uv run motif-balance design design.yaml \
  --out /tmp/motif-balance-result

# Verify the saved scores and print the sequences and their motif matches.
uv run motif-balance inspect /tmp/motif-balance-result
```

The best balance is approximately **0.855**: the weaker of the two best motif
matches, scored relative to its model's possible range.

Use a new output directory when rerunning. The saved directory contains the
request, input motifs, sequences, match tables and search record.

## 2. View the sequence and its motif matches

```bash
# Draw the best candidate as double-stranded DNA with aligned motif logos.
uv run motif-balance inspect /tmp/motif-balance-result \
  --format svg --view candidate --out /tmp/motif-balance-candidate.svg

# Create a browser view of the candidate set and its scores.
uv run motif-balance inspect /tmp/motif-balance-result \
  --format html --out /tmp/motif-balance-review.html
```

Open the SVG in an image viewer or the HTML in a browser. The filled windows
show the selected best match to each motif; the logos show its base preferences.
These exports leave the saved result unchanged.

## 3. Change the design question

Edit a copy of the [request](../examples/argr-cra/design.yaml):

| Setting | What it changes |
| --- | --- |
| `length` | Available DNA; every motif must fit |
| `direction: seek` or `avoid` | Favor or reduce that motif's strongest match |
| `count` | Number of returned sequences |
| `evaluations` | Number of candidate scores the search may compute |
| `seed` | Random starting choices and search proposals |

Run `--check` before searching the edited request. To select different motif
arrangements, continue with [collections](choose-alternatives.md). For a
twelve-model application and recorded search, follow the [example](../examples/twelve-motifs/README.md).

## Compare search methods

Keep the same request, seed and evaluation allowance while changing the method:

```bash
for method in annealed greedy random; do
  uv run motif-balance design design.yaml \
    --method "$method" --out "/tmp/motif-balance-$method"
done
```

Use new output directories. Annealed search is the default. Greedy accepts only
improving single-base changes; random search samples whole sequences with
replacement. The output records the engine used. Equal evaluation allowances do
not imply equal elapsed time. See the
[Python comparison](python-api.md#compare-search-methods) and
[method definitions](methods.md#explicit-comparison-methods).

Complete enumeration is a separate `--method exhaustive` request whose budget
must cover every possible sequence. The guided methods keep their named update
rules even when the sequence space is small.
