"""
--------------------------------------------------------------------------------
motif-balance
tests/contract/test_search_regression.py

Verify search regression behavior.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import hashlib
import json

import pytest

from motif_balance import DesignSpec, MotifModel, MotifSpecification, design

# Directional behavior captured before removing hard-ceiling branches.
# Identities of packaging and record schemas are deliberately not search outcomes.
_EXPECTED = {
    ("seek", 2, 16): (
        "bedd8e189db8c9d7c92792e40da00c707c9ca5b2478e8a38a536a1daad25f754",
        "bedd8e189db8c9d7c92792e40da00c707c9ca5b2478e8a38a536a1daad25f754",
        "fabe4e7b0799810a24cbff704b38a7d713e81090c06788ecd46eb825b9be33eb",
    ),
    ("seek", 6, 64): (
        "1e57ad4569d26228712a4b2f6218ec2b9f4b3cdcba4907cae166e4b4fbd38145",
        "b59baa2fe005308bba53747bc91305068692620ff2e7895417822070f10d254f",
        "ce4e5e35d43c673108567772c687a469fc100c78453a5bce028a12f5eacda539",
    ),
    ("seek", 6, 128): (
        "f38ab6c87d018703ee85370675582145efa2e872638fc776d7b559dc2fbd349b",
        "9ac74aa21ffc8dd86720004a86ba5d6e0d7b4584c4ded53ce3f75f4c5abd9e13",
        "db2a5152eb857c064c730c5d240a20bb02de401866858db8aa80ca69e43fb6ca",
    ),
    ("avoid", 2, 16): (
        "3dc0e4560814ee4f3bb89960ca670ff23ea05f16a8d6e0c37ce6892daf01ca5d",
        "3dc0e4560814ee4f3bb89960ca670ff23ea05f16a8d6e0c37ce6892daf01ca5d",
        "bbec1c1bf5a8fad1b5e4ea8f5f6030a6de9e8ecfa2350438ef1523962b5c31a0",
    ),
    ("avoid", 6, 64): (
        "e79792bc753bd1d66de80a279970772c79fb50e1bc5bace444ad8099fa73b0af",
        "1e080cb0e43da9747ae1e849b76c3f3968e99f115a8dc77fb123bfdf83872257",
        "33a1e0a13454460fec3d6c25bc4eb3a00eba01a30fcdf7207fd590a1f84e873e",
    ),
    ("avoid", 6, 128): (
        "c4403d2034278ff6bd71ca9591d717ae75a5044e4b07baa41543217c6b4d4ba3",
        "5671bc602f295647b2315fdfcb6b1a7988f2083cf7c969b20e1d3a52c1788651",
        "a83acceefb8b7de52dc23909fe9b927f107a63954523e8f45570ebe0a11f9647",
    ),
}


def _scored(item):
    return {
        "sequence": item.sequence,
        "balance_score": item.balance_score,
        "matches": [match.model_dump(mode="json") for match in item.matches],
    }


@pytest.mark.parametrize(("direction", "length", "budget"), _EXPECTED)
@pytest.mark.parametrize(("index", "method"), tuple(enumerate(("annealed", "greedy", "random"))))
def test_directional_search_outcomes_survive_contract_cleanup(
    direction, length, budget, index, method
):
    models = tuple(
        MotifModel(motif_id=name, probabilities=rows, background=(0.25,) * 4)
        for name, rows in (
            ("a", ((0.7, 0.1, 0.1, 0.1), (0.1, 0.7, 0.1, 0.1))),
            ("b", ((0.1, 0.1, 0.7, 0.1), (0.1, 0.1, 0.1, 0.7))),
        )
    )
    spec = DesignSpec(
        specifications=(
            MotifSpecification(motif=models[0], direction="seek"),
            MotifSpecification(motif=models[1], direction=direction),
        ),
        length=length,
        count=1,
        strands="both",
        evaluations=budget,
        seed=7,
    )
    portfolio = design(spec, method=method)
    manifest = portfolio.manifest
    diagnostics = manifest.search_diagnostics
    payload = {
        "candidates": [_scored(x) for x in portfolio.candidates],
        "elites": [_scored(x) for x in manifest.elites],
        "best": _scored(manifest.best_observed),
        "evaluations": manifest.evaluation_count,
        "unique": manifest.unique_evaluations,
        "engine": manifest.search_engine,
        "restarts": diagnostics.restarts,
        "checkpoints": [x.model_dump(mode="json") for x in diagnostics.checkpoints],
        "final_scores": diagnostics.restart_final_scores,
        "proposals": [x.model_dump(mode="json") for x in diagnostics.proposals],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(encoded).hexdigest() == _EXPECTED[direction, length, budget][index]
