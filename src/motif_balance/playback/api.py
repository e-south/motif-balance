"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/playback/api.py

Replay recorded searches and project their actual DNA states for playback.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

import hashlib
import math

from motif_balance.api import read_search_observation, verify_search_observation
from motif_balance.errors import ArtifactError
from motif_balance.inspection.supplied import inspect_candidate
from motif_balance.model import Candidate
from motif_balance.model.evaluation import candidate_id_for_sequence
from motif_balance.model.search_observation import SearchObservation

from .model import PlaybackFrame, PlaybackInspection


def inspect_playback(
    observation: SearchObservation | bytes, *, chain_id: int | None = None
) -> PlaybackInspection:
    """Verify a search before presenting its sampled best states or one fixed chain.

    Replay costs another search. No inferred intermediate sequences or mixed-chain
    trajectories are constructed. Candidate projection then checks each score and site.
    """
    if chain_id is not None and (type(chain_id) is not int or not 0 <= chain_id < 8):
        raise ArtifactError("chain must be an integer from 0 through 7, or omitted")
    if isinstance(observation, bytes):
        # Parse and check presentation bounds before the potentially expensive replay.
        if len(observation) > 64 * 1024 * 1024:
            raise ArtifactError("playback observation exceeds the 64 MiB input limit")
        checked = SearchObservation.model_validate_json(observation)
    elif isinstance(observation, SearchObservation):
        checked = SearchObservation.model_validate(observation.model_dump(mode="python"))
    else:
        raise ArtifactError("playback requires a SearchObservation or its JSON bytes")
    if checked.spec.length > 128 or len(checked.spec.specifications) > 8:
        raise ArtifactError("compact playback supports at most 128 bases and eight motifs")
    if any(
        not math.isclose(p, 0.25, abs_tol=1e-12)
        for item in checked.spec.specifications
        for p in item.motif.background
    ):
        raise ArtifactError("information-logo playback requires a uniform scoring background")
    if chain_id is not None and any(chain_id >= len(row.states) for row in checked.snapshots):
        raise ArtifactError("the recorded search does not contain that chain")
    if isinstance(observation, bytes):
        checked = read_search_observation(observation)
    else:
        verify_search_observation(checked)
    frames = []
    for row in checked.snapshots:
        evaluation = row.incumbent if chain_id is None else row.states[chain_id].evaluation
        candidate = Candidate(
            **evaluation.model_dump(mode="python"),
            candidate_id=candidate_id_for_sequence(evaluation.sequence),
            rank=1,
        )
        projection = inspect_candidate(candidate, checked.spec)
        frames.append(
            PlaybackFrame(
                evaluations=row.evaluations,
                best_balance=row.incumbent.balance_score,
                candidate=projection.candidate,
            )
        )
    return PlaybackInspection(
        observation_sha256=hashlib.sha256(checked.model_dump_json().encode()).hexdigest(),
        problem=projection.problem,
        engine=checked.engine,
        chain_id=chain_id,
        frames=tuple(frames),
    )
