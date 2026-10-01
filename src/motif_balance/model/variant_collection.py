"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/model/variant_collection.py

Separate checked products for every selected arrangement in one collection.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from typing import Literal, Self

from pydantic import model_validator

from .alternatives import CollectionReport
from .base import FrozenModel
from .variants import VariantLibrary


class CollectionVariants(FrozenModel):
    schema_version: Literal["collection-variants/v1"] = "collection-variants/v1"
    source: CollectionReport
    libraries: tuple[VariantLibrary, ...]

    @model_validator(mode="after")
    def bind_members(self) -> Self:
        if not self.libraries or len(self.libraries) != self.source.collection.delivered_count:
            raise ValueError("one library is required for every delivered collection member")
        first = self.libraries[0]
        for member, library in zip(self.source.collection.members, self.libraries, strict=True):
            if library.parent != member.evaluation or library.spec != self.source.ranking.spec:
                raise ValueError("libraries must retain their collection parents and request")
            if (
                library.min_balance,
                library.max_score_loss,
                library.max_variants,
                library.construction_order,
            ) != (
                first.min_balance,
                first.max_score_loss,
                first.max_variants,
                first.construction_order,
            ):
                raise ValueError("collection libraries must share construction settings")
        return self

    @property
    def unique_sequences(self) -> tuple[str, ...]:
        """Literal supplied strands, without merging their ambiguity templates."""
        return tuple(sorted({v.sequence for lib in self.libraries for v in lib.variants}))
