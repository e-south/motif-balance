"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/__init__.py

Expose motif models, design requests, sequence scoring, and DNA design.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from motif_balance.api import Portfolio, design, score
from motif_balance.constants import PACKAGE_VERSION as __version__
from motif_balance.model import (
    Candidate,
    DesignSpec,
    MotifMatch,
    MotifModel,
    MotifSpecification,
)

__all__ = [
    "Candidate",
    "DesignSpec",
    "MotifMatch",
    "MotifModel",
    "MotifSpecification",
    "Portfolio",
    "design",
    "score",
]
