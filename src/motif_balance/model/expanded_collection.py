"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/model/expanded_collection.py

Bind each explicit sequence expansion to its selected collection member.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from typing import Literal, Self

from pydantic import model_validator

from .alternatives import CollectionReport
from .base import FrozenModel
from .sequence_expansion import SequenceExpansion


class ExpandedCollection(FrozenModel):
    schema_version: Literal["expanded-collection/v1"] = "expanded-collection/v1"
    source: CollectionReport
    libraries: tuple[SequenceExpansion, ...]

    @model_validator(mode="after")
    def bind_members(self) -> Self:
        if not self.libraries or len(self.libraries) != self.source.collection.delivered_count:
            raise ValueError("one expansion is required for each delivered arrangement")
        settings = {(v.min_balance, v.max_variants, v.max_evaluations) for v in self.libraries}
        if len(settings) != 1:
            raise ValueError("collection members must use the same expansion settings")
        for library, member in zip(self.libraries, self.source.collection.members, strict=True):
            if library.parent != member.evaluation or library.spec != self.source.ranking.spec:
                raise ValueError("expansion must retain its collection parent and request")
        return self

    @property
    def unique_sequences(self) -> tuple[str, ...]:
        return tuple(sorted({v.sequence for lib in self.libraries for v in lib.variants}))
