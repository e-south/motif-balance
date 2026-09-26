"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/formats/variants.py

Concrete sequence and score exports for a checked variant library.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import csv
import io

from motif_balance.model.variants import VariantLibrary


def variants_fasta(library: VariantLibrary) -> str:
    return "".join(
        f">variant-{i} balance={v.balance_score:.12g}\n{v.sequence}\n"
        for i, v in enumerate(library.variants, 1)
    )


def variants_tsv(library: VariantLibrary) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
    writer.writerow(
        (
            "variant",
            "sequence",
            "balance",
            "motif_id",
            "direction",
            "score",
            "component_change",
            "start",
            "end",
            "strand",
        )
    )
    for i, v in enumerate(library.variants, 1):
        for parent, m in zip(library.parent.matches, v.matches, strict=True):
            writer.writerow(
                (
                    i,
                    v.sequence,
                    v.balance_score,
                    m.motif_id,
                    m.spec_direction,
                    m.normalized_score,
                    m.spec_satisfaction - parent.spec_satisfaction,
                    m.start,
                    m.end,
                    m.strand,
                )
            )
    return stream.getvalue()
