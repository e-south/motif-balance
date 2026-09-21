# ArgR and Cra

Design 32-base DNA with matches to the *Escherichia coli* transcription factors
ArgR and Cra. Their profiles span 25 and 14 positions, so matches must overlap
within this length. The [top-level example](../../README.md#try-a-design)
loads these models from Python; [First design](../../docs/quickstart.md) uses
the same request from the command line.

The numerical matrices come from **Baumgart et al. (2021), Supplementary Data 2**,
[Persistence and plasticity in bacterial gene regulation](https://doi.org/10.1038/s41592-021-01312-2).
They were inferred from DAP-seq experiments. [SOURCE.json](SOURCE.json) identifies
the original archive members, retrieval URL and checksums.

- `source/` contains the extracted nucleotide probabilities and source backgrounds.
- `motifs/` contains the prepared models consumed by the design request.
- `design.yaml` fixes the length, requested count, evaluation budget and seed.

To prepare each position, we divide its four source values by their sum to
remove decimal rounding error. We then mix these probabilities with a uniform
prior: `p = (p0 + 0.025) / 1.1`. The scoring background assigns 0.25 to each base.
This gives positive probabilities for every nucleotide. The original background
is retained in the conversion record.

```bash
# Verify that the bundled models reproduce this preparation from the source data.
uv run python examples/argr-cra/verify_inputs.py
# Check the request before searching.
uv run motif-balance design examples/argr-cra/design.yaml --check
# Search and save the four sequences in a new directory.
uv run motif-balance design examples/argr-cra/design.yaml --out /tmp/argr-cra-result
```

The source matrices are numerical research data attributed to the authors above.
The repository's software license does not relicense the source publication.
